import { fetchApi } from '$lib/api/client';
import { redirect } from "@sveltejs/kit";

export interface UserResponse {
    id: number;
    username: string;
    role: string | null;
    starred_tags: number[];
}

interface UserLogin {
    username: string;
    password: string;
    remember_me: boolean;
}

interface ChangePasswordRequest {
    old_password: string;
    new_password: string;
}

interface AuthOptions {
    password_enabled: boolean;
    oidc_enabled: boolean;
    oidc_provider_name: string;
}

interface OIDCAuthorizationURLResponse {
    url: string;
    random: number;
}

class AuthClient {
    private baseUrl: string;

    constructor(baseUrl: string = '/api/auth') {
        this.baseUrl = baseUrl;
    }

    async me(): Promise<UserResponse | null> {
        const response = await fetchApi(`${this.baseUrl}/me`);
        if (response.status === 401) {
            return null;
        }
        if (!response.ok) {
            throw new Error('Failed to get profile');
        }

        return response.json();
    }

    async login(username: string, password: string, rememberMe: boolean = false): Promise<UserResponse> {
        const response = await fetchApi(`${this.baseUrl}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            skipAuthRetry: true,
            body: JSON.stringify({
                username,
                password,
                remember_me: rememberMe
            } as UserLogin)
        });

        if (!response.ok) {
            throw new Error('Login failed');
        }

        return response.json(); // Direct user response, no token handling
    }

    async logout(): Promise<void> {
        const response = await fetchApi(`${this.baseUrl}/logout`, {
            method: 'POST',
            skipAuthRetry: true
        });

        if (!response.ok) {
            throw new Error('Logout failed');
        }
    }

    async changePassword(oldPassword: string, newPassword: string): Promise<UserResponse> {
        const response = await fetchApi(`${this.baseUrl}/change-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            skipAuthRetry: true,
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword
            } as ChangePasswordRequest)
        });

        if (!response.ok) {
            throw new Error('Password change failed');
        }

        return response.json();
    }

    async register(username: string, password: string): Promise<UserResponse> {
        const response = await fetchApi(`${this.baseUrl}/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            skipAuthRetry: true,
            body: JSON.stringify({
                username,
                password,
                remember_me: false
            } as UserLogin)
        });

        if (!response.ok) {
            throw new Error('Registration failed');
        }

        return response.json();
    }

    async refresh(): Promise<UserResponse> {
        const response = await fetchApi(`${this.baseUrl}/refresh`, {
            method: 'POST',
            skipAuthRetry: true
        });

        if (!response.ok) {
            throw new Error('Token refresh failed');
        }

        return response.json();
    }

    async options(): Promise<AuthOptions> {
        const response= await fetchApi(`${this.baseUrl}/options`, {
            skipAuthRetry: true,
        });

        if (!response.ok) {
            throw new Error('Could not fetch authentication options');
        }

        return response.json();
    }

    async OIDCAuthorize(): Promise<OIDCAuthorizationURLResponse> {
        const response = await fetchApi(`${this.baseUrl}/oidc/authorize`, {
            skipAuthRetry: true,
        })

        if (!response.ok) {
            throw new Error('OIDC authorize failed');
        }

        return response.json();
    }
}

export const authClient = new AuthClient(); 
