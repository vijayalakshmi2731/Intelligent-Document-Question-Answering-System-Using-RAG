import io, os, sys, tempfile, time
from pathlib import Path

os.environ["DOCQA_DATA_DIR"] = tempfile.mkdtemp()
os.environ["OPENAI_API_KEY"] = ""  # deterministic offline mode
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import docx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.chunking import chunk_units, clean_text

client = TestClient(app)

TEXT = ("Photosynthesis is the process by which green plants convert sunlight into chemical energy. "
        "It takes place in the chloroplasts, which contain chlorophyll. " * 3 +
        "\n\nThe Eiffel Tower was completed in 1889 and stands 330 metres tall in Paris. "
        "It was designed by the engineering company of Gustave Eiffel.\n\n"
        "Python is a programming language created by Guido van Rossum and first released in 1991.")


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)


def wait_ready(h, doc_id):
    for _ in range(50):
        d = client.get(f"/api/documents/{doc_id}", headers=h).json()
        if d["status"] != "processing":
            return d
        time.sleep(0.1)
    raise AssertionError("timeout")


@pytest.fixture(scope="module")
def admin():
    r = client.post("/api/auth/register", json={"name": "Ada", "email": "ada@example.com", "password": "password123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture(scope="module")
def user2():
    r = client.post("/api/auth/register", json={"name": "Bob", "email": "bob@example.com", "password": "password123"})
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_auth(admin):
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/register", json={"name": "x", "email": "ada@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrongpass1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ada@example.com", "password": "password123"}).status_code == 200
    assert client.get("/api/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_pipeline_and_isolation(admin, user2):
    r = client.post("/api/documents", headers=admin, files={"file": ("facts.txt", TEXT.encode())})
    doc = wait_ready(admin, r.json()["id"])
    assert doc["status"] == "ready" and doc["chunk_count"] >= 1

    # pdf + docx
    r = client.post("/api/documents", headers=admin, files={"file": ("paris.pdf", make_pdf("The Louvre in Paris is the largest art museum in the world."))})
    assert wait_ready(admin, r.json()["id"])["status"] == "ready"
    d = docx.Document(); d.add_heading("Oceans", 1); d.add_paragraph("The Pacific Ocean is the largest and deepest ocean on Earth.")
    buf = io.BytesIO(); d.save(buf)
    r = client.post("/api/documents", headers=admin, files={"file": ("oceans.docx", buf.getvalue())})
    dd = wait_ready(admin, r.json()["id"])
    assert dd["status"] == "ready" and dd["chunks"][0]["section"] == "Oceans"

    # grounded answer with sources
    a = client.post("/api/chat", headers=admin, json={"question": "When was the Eiffel Tower completed?"}).json()
    assert "1889" in a["answer"] and a["sources"][0]["filename"] == "facts.txt"
    a2 = client.post("/api/chat", headers=admin, json={"question": "Which ocean is the deepest?"}).json()
    assert "Pacific" in a2["answer"]
    a3 = client.post("/api/chat", headers=admin, json={"question": "How tall is it?", "conversation_id": a["conversation_id"]}).json()
    assert "330" in a3["answer"]                      # follow-up resolved via history

    # hallucination control
    out = client.post("/api/chat", headers=admin, json={"question": "Explain quantum chromodynamics gluon confinement"}).json()
    assert out["meta"]["answered"] is False and out["sources"] == []

    # isolation
    assert client.get("/api/documents", headers=user2).json() == []
    assert client.post("/api/chat", headers=user2, json={"question": "When was the Eiffel Tower completed?"}).json()["meta"]["answered"] is False
    assert client.get(f"/api/documents/{doc['id']}", headers=user2).status_code == 404

    # validation
    assert client.post("/api/documents", headers=admin, files={"file": ("x.exe", b"abc")}).status_code == 400
    assert client.post("/api/documents", headers=admin, files={"file": ("e.txt", b"")}).status_code == 400
    r = client.post("/api/documents", headers=admin, files={"file": ("blank.txt", b"   \n  ")})
    assert wait_ready(admin, r.json()["id"])["status"] == "failed"

    # explorer, eval, admin, delete
    assert client.get("/api/search", params={"q": "Eiffel"}, headers=admin).json()
    ev = client.post("/api/evaluation/run", headers=admin, json={"n_synthetic": 5}).json()
    assert ev["summary"]["hit@5"] >= 0.8 and ev["unanswerable"]["abstention_rate"] >= 0.66
    assert client.get("/api/admin/stats", headers=admin).json()["users"] == 2
    assert client.get("/api/admin/stats", headers=user2).status_code == 403
    assert client.get("/api/admin/report.csv", headers=admin).status_code == 200
    assert client.delete(f"/api/documents/{doc['id']}", headers=admin).status_code == 200


def test_chunking():
    units = [{"page": 3, "section": "S", "text": ("Sentence number one is here. " * 80)}]
    ch = chunk_units(units, 300, 60)
    assert len(ch) > 3 and all(c["page"] == 3 and len(c["text"]) <= 420 for c in ch)
    assert "-" not in clean_text("exam-\nple")
