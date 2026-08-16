const API_URL = import.meta.env.VITE_API_URL as string;

export interface TokenResponse {
  token: string;
  url: string;
  room: string;
}

export async function fetchCallToken(identity = "caller"): Promise<TokenResponse> {
  const res = await fetch(`${API_URL}/api/token?identity=${encodeURIComponent(identity)}`);
  if (!res.ok) {
    throw new Error(`token request failed: ${res.status}`);
  }
  return res.json();
}
