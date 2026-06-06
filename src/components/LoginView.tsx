import React, { useState } from 'react';
import { Loader2, LockKeyhole, LogIn } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export function LoginView() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('ChangeMe123!');
  const [submitting, setSubmitting] = useState(false);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-6 text-slate-900">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-600 text-white">
            <LockKeyhole size={20} />
          </div>
          <div>
            <p className="text-lg font-bold tracking-tight">Xpatweb AI</p>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Secure Review Access</p>
          </div>
        </div>

        <form
          className="space-y-4"
          onSubmit={async event => {
            event.preventDefault();
            setSubmitting(true);
            try {
              await login(email, password);
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <label className="block space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={event => setEmail(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition-all focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={event => setPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition-all focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
            />
          </label>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-sm font-bold text-white transition-colors hover:bg-slate-800 disabled:bg-slate-400"
          >
            {submitting ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
