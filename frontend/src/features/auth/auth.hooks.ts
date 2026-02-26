import { useCallback, useEffect, useState } from 'react';
import { getProfile, login as loginApi, type LoginCredentials } from './auth.api';
import { useAuth } from './AuthContext';

export function useLogin() {
  const { login: setToken } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      setIsLoading(true);
      setError(null);
      try {
        const { access_token } = await loginApi(credentials);
        setToken(access_token);
        return true;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Login failed';
        setError(message);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [setToken]
  );

  return { login, isLoading, error };
}

export function useProfile() {
  const { token } = useAuth();
  const [username, setUsername] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setUsername(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    getProfile(token)
      .then((data) => {
        if (!cancelled) setUsername(data.username);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load profile');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  return { username, isLoading, error };
}
