/**
 * Base API client for MultiBinder
 * Handles JWT auth via localStorage and Bearer token header
 */
const API = {
    getToken: () => localStorage.getItem('token'),

    async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        const token = this.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const opts = { method, headers };
        if (body !== null) opts.body = JSON.stringify(body);

        try {
            const res = await fetch(path, opts);

            if (res.status === 401) {
                localStorage.removeItem('token');
                window.location.href = '/login';
                return null;
            }

            if (res.status === 204) {
                return { success: true };
            }

            return await res.json();
        } catch (err) {
            console.error(`API ${method} ${path} failed:`, err);
            return null;
        }
    },

    get: (path) => API.request('GET', path),
    post: (path, body) => API.request('POST', path, body),
    put: (path, body) => API.request('PUT', path, body),
    delete: (path) => API.request('DELETE', path),
};
