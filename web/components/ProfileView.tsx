"use client";
import { useState } from "react";
import { api, User } from "@/lib/api";
import { PageHeader, useToast } from "./ui";

export default function ProfileView({ user, onUpdate }: { user: User; onUpdate: (u: User) => void }) {
  const toast = useToast();
  const [f, setF] = useState({ name: user.name, bio: user.bio || "", password: "", current_password: "" });
  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/me", { method: "PUT", body: { name: f.name, bio: f.bio, password: f.password || null, current_password: f.current_password || null } });
      onUpdate(await api<User>("/me"));
      setF({ ...f, password: "", current_password: "" });
      toast("Profile saved");
    } catch (e: any) { toast(e.message); }
  }
  return (
    <>
      <PageHeader title="Profile" subtitle="Manage your account details." />
      <form onSubmit={save} className="card max-w-xl space-y-4 p-6">
        <label className="block text-sm font-medium">Email<input className="input mt-1.5 opacity-60" value={user.email} disabled /></label>
        <label className="block text-sm font-medium">Name<input className="input mt-1.5" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label className="block text-sm font-medium">Bio<textarea className="input mt-1.5" rows={3} value={f.bio} onChange={(e) => setF({ ...f, bio: e.target.value })} /></label>
        <hr className="border-zinc-200 dark:border-zinc-800" />
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium">Current password<input className="input mt-1.5" type="password" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></label>
          <label className="block text-sm font-medium">New password<input className="input mt-1.5" type="password" minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
        </div>
        <button className="btn-primary">Save changes</button>
      </form>
    </>
  );
}
