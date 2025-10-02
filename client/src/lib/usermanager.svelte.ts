import { goto } from "$app/navigation";
import { page } from "$app/state";
import { authClient, type UserResponse } from "../auth";

export class UserManager {
    public loggedIn = $state(false);
    // private _user: UserResponse | null = null;
    public user = $state<UserResponse>({
        id: 0,
        username: '',
        role: null,
        starred_tags: []
    });
    public starredTagIds = $state<number[]>([]);


    async init(pathname: string) {
        if (pathname.startsWith('/users/login')) {
            return;
        }

        const user = await authClient.me();
        if (user === null) {
            console.log('User is not logged in');
            // Only redirect if we're not already on the login page
            if (!page.url.pathname.startsWith('/users/login')) {
                console.log('redirecting to', encodeURIComponent(window.location.href));
                await goto('/users/login?redirect=' + encodeURIComponent(window.location.href));
            }
            return;
        }

        this.user = user;
        this.starredTagIds = user.starred_tags ?? [];

        // await this.setCreator(user.id);
    }

    async login(username: string, password: string, rememberMe: boolean) {
        this.user = await authClient.login(username, password, rememberMe);
        this.starredTagIds = this.user.starred_tags ?? [];
        // await this.setCreator(resp.id);

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
        this.user = {
            id: 0,
            username: '',
            role: null,
            starred_tags: []
        };
        this.starredTagIds = [];
        goto('/users/login');
    }

    async changePassword(oldPassword: string, newPassword: string) {
        const user = await authClient.changePassword(oldPassword, newPassword);
        this.user = user; 
        this.starredTagIds = user.starred_tags ?? this.starredTagIds;
    }

    // private async setCreator(id: number) {
    //     await loadBase();
    //     const { creators } = data;
    //     this._creator = creators.get(id) ?? null;
    // }

    async signup(username: string, password: string) {
        const user = await authClient.register(username, password);
        this.user = user; 
        this.starredTagIds = user.starred_tags ?? [];
    }
}