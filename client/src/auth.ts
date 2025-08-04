interface UserResponse {
    id: number;
    username: string;
    role: string | null;
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

class AuthClient {
    private baseUrl: string;

    constructor(baseUrl: string = '/api/auth') {
        this.baseUrl = baseUrl;
    }

    async getProfile(): Promise<UserResponse | null> {
        const response = await fetch(`${this.baseUrl}/me`, {
            method: 'GET',
            credentials: 'include'
        });
        if (response.status === 401) {
            // Try to refresh the token
            try {
                return await this.refresh();
            } catch {
                return null;
            }
        }
        if (!response.ok) {
            throw new Error('Failed to get profile');
        }

        return response.json();
    }

    async login(username: string, password: string, rememberMe: boolean = false): Promise<UserResponse> {
        const response = await fetch(`${this.baseUrl}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
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
        const response = await fetch(`${this.baseUrl}/logout`, {
            method: 'POST',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Logout failed');
        }
    }

    async changePassword(oldPassword: string, newPassword: string): Promise<UserResponse> {
        const response = await fetch(`${this.baseUrl}/change-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
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
        const response = await fetch(`${this.baseUrl}/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
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
        const response = await fetch(`${this.baseUrl}/refresh`, {
            method: 'POST',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Token refresh failed');
        }

        return response.json();
    }
}

export const authClient = new AuthClient(); 