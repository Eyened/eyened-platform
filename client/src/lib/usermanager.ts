import { goto } from "$app/navigation";
import { page } from "$app/state";
import { authClient } from "../auth";
import { loadBase } from "./datamodel/api.svelte";
import { type Creator } from "./datamodel/creator.svelte";
import { data } from "./datamodel/model";

export class UserManager {

    private _creator: Creator | null = null;

    constructor() {
    }

    async init(pathname: string) {
        if (pathname.startsWith('/users/login')) {
            return;
        }

        const user = await authClient.getProfile();
        if (user === null) {
            console.log('User is not logged in');
            // Only redirect if we're not already on the login page
            if (!page.url.pathname.startsWith('/users/login')) {
                console.log('redirecting to', encodeURIComponent(window.location.href));
                await goto('/users/login?redirect=' + encodeURIComponent(window.location.href));
            }
            return;
        }

        await this.setCreator(user.id);
    }

    async login(username: string, password: string, rememberMe: boolean) {
        const resp = await authClient.login(username, password, rememberMe);
        await this.setCreator(resp.id);

        // Get the redirect URL from the query parameters
        const params = new URLSearchParams(window.location.search);
        const redirectUrl = params.get('redirect');

        // If there's a redirect URL, go there, otherwise go to the root
        if (redirectUrl) {
            await goto(decodeURIComponent(redirectUrl));
        } else {
            await goto('/');
        }
    }

    async logout() {
        await authClient.logout();
        this._creator = null;
        goto('/users/login');
    }

    async changePassword(oldPassword: string, newPassword: string) {
        const resp = await authClient.changePassword(oldPassword, newPassword);

    }

    private async setCreator(id: number) {
        await loadBase();
        const { creators } = data;
        this._creator = creators.get(id) ?? null;
    }

    get creator(): Creator {
        if (!this._creator) {
            throw new Error('Creator not found');
        }
        return this._creator;
    }

    async signup(username: string, password: string) {
        await authClient.register(username, password);
    }

}