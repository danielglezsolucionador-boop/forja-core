const rawApiUrl = process.env.REACT_APP_FORJA_API_URL || "";

export const API_BASE_URL = rawApiUrl.replace(/\/$/, "");

export function apiUrl(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}
