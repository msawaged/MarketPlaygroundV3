// Accounts on the client: a session token plus the account's id, kept in this browser.
import { useEffect, useState } from 'react';
import { request, userId } from './api';

const T = 'mp_token', A = 'mp_account', U = 'mp_user_id';

function read(k) { try { return localStorage.getItem(k); } catch { return null; } }
function write(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ } }
function announce() { window.dispatchEvent(new Event('mp-auth')); }

export function currentAccount() {
  try { return JSON.parse(read(A) || 'null'); } catch { return null; }
}

function adopt(res) {
  write(T, res.token);
  write(A, JSON.stringify(res.account));
  write(U, res.account.uid); // this device now acts as the account everywhere (beliefs, practice, votes)
  announce();
  return res;
}

export async function signup({ email, password, name }) {
  const res = await request('/v4/auth/signup', { method: 'POST', body: { email, password, name, device_id: userId() } });
  return res.needs_verification ? res : adopt(res);  // with email set up, the account opens after the link is tapped
}

export async function verifyEmail(token) {
  return adopt(await request('/v4/auth/verify', { method: 'POST', body: { token, device_id: userId() } }));
}

export function resendVerification(email) {
  return request('/v4/auth/resend', { method: 'POST', body: { email } });
}

export function forgotPassword(email) {
  return request('/v4/auth/forgot', { method: 'POST', body: { email } });
}

export async function resetPassword(token, password) {
  return adopt(await request('/v4/auth/reset', { method: 'POST', body: { token, password } }));
}

export async function login({ email, password }) {
  return adopt(await request('/v4/auth/login', { method: 'POST', body: { email, password, device_id: userId() } }));
}

export async function logout() {
  try { await request('/v4/auth/logout', { method: 'POST' }); } catch { /* already gone */ }
  write(T, null); write(A, null);
  write(U, null); // fresh anonymous id, so the next person on this device starts clean
  userId();
  announce();
}

export async function refreshAccount() {
  if (!read(T)) return null;
  try {
    const { account } = await request('/v4/auth/me');
    write(A, JSON.stringify(account)); announce();
    return account;
  } catch (e) {
    if (e.status === 401) { write(T, null); write(A, null); announce(); }
    return currentAccount();
  }
}

export async function updateName(name) {
  const { account } = await request('/v4/auth/profile', { method: 'POST', body: { name } });
  write(A, JSON.stringify(account)); announce();
  return account;
}

export function changePassword(current, next) {
  return request('/v4/auth/password', { method: 'POST', body: { current, new: next } });
}

export async function deleteAccount(password) {
  await request('/v4/auth/delete', { method: 'POST', body: { password } });
  write(T, null); write(A, null); write(U, null); userId(); announce();
}

/** React hook: the signed-in account (or null), kept in sync across the app. */
export function useAccount() {
  const [acc, setAcc] = useState(currentAccount);
  useEffect(() => {
    const on = () => setAcc(currentAccount());
    window.addEventListener('mp-auth', on);
    window.addEventListener('storage', on);
    return () => { window.removeEventListener('mp-auth', on); window.removeEventListener('storage', on); };
  }, []);
  return acc;
}

export function initials(acc) {
  const s = (acc?.name || acc?.email || '?').trim();
  return s.charAt(0).toUpperCase();
}
