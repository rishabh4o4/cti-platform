/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { Shield } from 'lucide-react';
import api from '@/lib/api';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const setToken = useAuthStore((state) => state.setToken);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (username && password) {
      try {
        const res = await api.post('/auth/token', { username, password });
        setToken(res.data.access_token);
        navigate('/');
      } catch (err: any) {
        if (err.response?.status === 401) {
          setError('Invalid username or password.');
        } else if (err.response?.status === 429) {
          setError('Too many attempts. Please try again later.');
        } else {
          setError('Failed to connect to the server.');
        }
      }
    } else {
      setError('Please provide valid credentials');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="bg-surface p-8 rounded-xl border border-border shadow-2xl w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">Intelligence Platform</h1>
          <p className="text-text-secondary text-sm mt-1">Sign in to access the dashboard</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1" htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-4 py-2 text-text-primary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
              placeholder="Enter your username"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-4 py-2 text-text-primary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
              placeholder="••••••••"
            />
          </div>
          
          {error && <p className="text-critical text-sm">{error}</p>}

          <button
            type="submit"
            className="w-full bg-primary hover:bg-primary/90 text-white font-medium py-2 px-4 rounded-lg transition-colors mt-6"
          >
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}
