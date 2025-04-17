import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { apiUrl, authTokenDuration } from '$lib/config';

export interface TokenData {
    id: number;
    role: number;
}

// Helper functions for localStorage operations
function safeGetItem(key: string): string | null {
    if (browser) {
        return localStorage.getItem(key);
    }
    return null;
}

function safeSetItem(key: string, value: string): void {
    if (browser) {
        localStorage.setItem(key, value);
    }
}

function safeRemoveItem(key: string): void {
    if (browser) {
        localStorage.removeItem(key);
    }
}

function getIntFromLocalStorage(key: string): number | null {
    const value = safeGetItem(key);
    if (value === null || value === 'undefined') {
        return null;
    }
    const parsedValue = parseInt(value, 10);
    return isNaN(parsedValue) ? null : parsedValue;
}

export class UserManager {

    // TODO: make this class save settings separately per user using the CreatorID as preffix for the stored settings

    private logged = false
    private role: number | null = null
    private creatorID: number | null = null
    private loginTimestamp: Date | null = null

    private readonly settings: Map<string, any>;

    constructor() {
        this.settings = new Map();
        this.readTokenData()

        console.log(`UserManager created with logged=${this.logged}, creatorID=${this.creatorID}, role=${this.role}`);
    }

    get isLoggedIn() {
        return this.logged;
    }

    get CreatorID() {
        return this.creatorID;
    }

    public setTokenData({ id, role }: TokenData) {
        safeSetItem('id', `${id}`);
        safeSetItem('role', `${role}`);
        safeSetItem('loginTimestamp', (new Date()).getTime().toString());
        this.readTokenData()
    }

    public readTokenData() {

        this.creatorID = getIntFromLocalStorage('id');
        this.role = getIntFromLocalStorage('role');

        const loginTimestampString = safeGetItem('loginTimestamp');
        this.loginTimestamp = loginTimestampString ? new Date(parseInt(loginTimestampString)) : null;

        if (this.creatorID !== null && this.loginTimestamp !== null) {
            // token was found in localStorage
            const secondsSince = (Date.now() - this.loginTimestamp.getTime()) / 1000
            if (secondsSince < authTokenDuration) {
                // user is logged in still
                this.logged = true

                if (secondsSince > authTokenDuration / 3) {
                    // user logged in for more than a day since last refresh
                    this.refresh()
                }
            } else {
                // token has expired (set >3 days ago)
                this.logged = false
            }
        } else {
            this.logged = false
        }
    }

    public async logout() {
        await fetch(`${apiUrl}/auth/logout`, {
            method: 'POST'
        });

        this.clearTokenData();
        goto(`/users/login`);
    };


    public async signup(username: string, password: string) {
        const resp = await fetch(`${apiUrl}/auth/register`, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        if (resp.ok) {
            alert('user created');
        } else {
            if (resp.status == 401) {
                alert('Unauthorized');
            } else if (resp.status == 400) {
                alert('Missing username or password');
            } else {
                alert('Unknown error');
            }
        }
    }

    public clearTokenData() {
        safeRemoveItem('id');
        safeRemoveItem('role');
        safeRemoveItem('loginTimestamp');
        this.readTokenData()
    }

    public async refresh() {
        const resp = await fetch(`${apiUrl}/auth/refresh`, {
            method: 'POST'
        });
        this.setTokenData(await resp.json())
    }

    public get(key: string, default_value: any): any {
        if (this.settings.has(key)) {
            return this.settings.get(key);
        } else {
            // try to get from cookies
            const value = Cookie.get(key);
            if (value == null) return default_value
            else return value
        }
    }

    public set(key: string, value: any): void {
        Cookie.set(key, value);
        this.settings.set(key, value);
    }

}

class Cookie {
    static get(name: string): string | null {
        const cookieName = `${encodeURIComponent(name)}=`;
        const cookie = document.cookie;
        let value = null;

        const startIndex = cookie.indexOf(cookieName);
        if (startIndex > -1) {
            let endIndex = cookie.indexOf(';', startIndex);
            if (endIndex == -1) {
                endIndex = cookie.length;
            }
            value = decodeURIComponent(
                cookie.substring(startIndex + name.length + 1, endIndex)
            );
        }
        return value;
    }

    static set(name: string, value: string | number | boolean, expires?: Date, path?: string, domain?: string, secure?: boolean) {
        let cookieText = `${encodeURIComponent(name)}=${encodeURIComponent(value.toString())}`;

        if (expires instanceof Date) {
            cookieText += `; expires=${expires.toUTCString()}`;
        } else {
            // cookie set for 7 days
            const sevenDaysFromNow = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
            cookieText += `; expires=${sevenDaysFromNow.toUTCString()}`;
        }

        if (path) cookieText += `; path=${path}`;
        if (domain) cookieText += `; domain=${domain}`;
        if (secure) cookieText += `; secure`;

        document.cookie = cookieText;
    }

    static remove(name: string, path: string, domain: string, secure: boolean) {
        Cookie.set(name, '', new Date(0), path, domain, secure);
    }
}