// Helper for API routing with subpath and authentication token support

export const getApiUrl = (path: string): string => {
  const isSubpath = window.location.pathname.startsWith('/grocery_list');
  const base = isSubpath ? '/grocery_list' : '';
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${cleanPath}`;
};

export const getAuthToken = (): string => {
  return localStorage.getItem('grocery_device_token') || '';
};

export const setAuthToken = (token: string): void => {
  localStorage.setItem('grocery_device_token', token);
};

export const clearAuthToken = (): void => {
  localStorage.removeItem('grocery_device_token');
};

export const apiFetch = async (path: string, init?: RequestInit): Promise<Response> => {
  const url = getApiUrl(path);
  const token = getAuthToken();

  const headers = new Headers(init?.headers || {});
  if (token && !headers.has('X-Device-Token')) {
    headers.set('X-Device-Token', token);
  }

  return fetch(url, {
    ...init,
    headers,
  });
};
