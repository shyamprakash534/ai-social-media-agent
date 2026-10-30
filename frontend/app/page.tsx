"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Post = { id: string; topic: string; draft: string; status: string; scheduled_for?: string | null; created_at?: string };

type Stats = { total: number; drafts: number; approved: number; scheduled: number; published: number; rejected: number };

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function refresh() {
    const [s, p] = await Promise.all([fetch(`${API}/api/stats`, { cache: "no-store" }), fetch(`${API}/api/posts`, { cache: "no-store" })]);
    if (!s.ok || !p.ok) throw new Error("API unavailable");
    setStats(await s.json());
    setPosts(await p.json());
  }

  useEffect(() => { refresh().catch(() => setMessage("Backend is starting or unavailable. Check the API URL.")); }, []);

  async function generate(e: FormEvent) {
    e.preventDefault(); if (!topic.trim()) return;
    setLoading(true); setMessage("");
    try {
      const r = await fetch(`${API}/api/posts/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic }) });
      if (!r.ok) throw new Error(await r.text());
      setTopic(""); await refresh(); setMessage("Draft generated. Review it below before approving.");
    } catch { setMessage("Could not generate the draft. Make sure the backend is running."); }
    finally { setLoading(false); }
  }

  async function action(id: string, type: "approve" | "reject") {
    const r = await fetch(`${API}/api/posts/${id}/${type}`, { method: "POST" });
    if (r.ok) { await refresh(); setMessage(`Post ${type}d.`); }
  }

  return (
    <main className="shell">
      <header className="topbar"><div><div className="eyebrow">ORBIT SOCIAL</div><h1>AI Social Media Agent</h1><p>Generate → review → approve → publish.</p></div><button className="ghost" onClick={() => refresh()}>Refresh</button></header>
      <section className="hero"><div><span className="pill">AI CONTENT WORKFLOW</span><h2>Turn ideas into publish-ready posts.</h2><p>Use the agent to create social content, keep a human approval step, and schedule publishing when your integrations are connected.</p></div><form onSubmit={generate} className="composer"><label>What should we post about?</label><textarea value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g. 5 practical ways AI is changing data analytics"/><button disabled={loading}>{loading ? "Generating…" : "Generate draft"}</button></form></section>
      {message && <div className="notice">{message}</div>}
      <section className="stats">{([["Total", stats?.total ?? 0],["Drafts", stats?.drafts ?? 0],["Approved", stats?.approved ?? 0],["Scheduled", stats?.scheduled ?? 0],["Published", stats?.published ?? 0]] as const).map(([label, value]) => <div className="stat" key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>
      <section className="panel"><div className="panelhead"><div><span className="eyebrow">CONTENT QUEUE</span><h3>Recent posts</h3></div><span className="muted">Human approval enabled</span></div>{posts.length === 0 ? <div className="empty">No posts yet. Generate your first draft above.</div> : <div className="posts">{posts.map(post => <article className="post" key={post.id}><div className="postmeta"><span className={`status ${post.status}`}>{post.status}</span><span>{post.topic}</span></div><p>{post.draft}</p><div className="actions">{post.status === "draft" && <><button onClick={() => action(post.id, "approve")}>Approve</button><button className="danger" onClick={() => action(post.id, "reject")}>Reject</button></>} {post.status === "approved" && <span className="muted">Ready to schedule or publish</span>}</div></article>)}</div>}</section>
      <footer>Demo mode is safe by default. Real LinkedIn publishing requires your own OAuth credentials and production integrations.</footer>
    </main>
  );
}
