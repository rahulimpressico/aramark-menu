const apiBase = import.meta.env.VITE_API_URL ?? '/api';
const LOGIN_PATH = '/token';
const USER_ME_PATH = '/users/me';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UserMeResponse {
  username: string;
}

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const body = new URLSearchParams({
    username: credentials.username,
    password: credentials.password,
  });
  const res = await fetch(`${apiBase}${LOGIN_PATH}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || 'Invalid credentials');
  }

  return res.json() as Promise<LoginResponse>;
}

export async function getProfile(token: string): Promise<UserMeResponse> {
  const res = await fetch(`${apiBase}${USER_ME_PATH}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || 'Failed to load profile');
  }

  return res.json() as Promise<UserMeResponse>;
}
