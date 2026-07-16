import { goto } from "$app/navigation";
import { page } from "$app/state";
import { authClient, type UserResponse } from "../auth";

export class UserManager {
    public user = $state<UserResponse>({
        id: -1,
        username: "",
        role: null,
        starred_tags: [],
    });
    public loggedIn = $derived(this.user.id !== -1);
    public starredTagIds = $state<number[]>([]);

    async init(pathname: string) {
        if (
            pathname.startsWith("/users/login") ||
            pathname.startsWith("/users/oidc-callback")
        ) {
            return;
        }

        const user = await authClient.me();
        if (user === null) {
            console.log("User is not logged in");
            // Only redirect if we're not already on the login page
            if (!page.url.pathname.startsWith("/users/login")) {
                console.log(
                    "redirecting to",
                    encodeURIComponent(window.location.href),
                );
                await goto(
                    "/users/login?next=" +
                        encodeURIComponent(window.location.href),
                );
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

        // Get the 'next' URL from the query parameters
        const params = new URLSearchParams(window.location.search);
        const nextUrl = params.get("next");

        // If there's a 'next' URL, go there, otherwise go to the root
        if (nextUrl) {
            await goto(decodeURIComponent(nextUrl));
        } else {
            await goto("/");
        }
    }

    async OIDCLogin(code: string, state: string) {
        this.user = await authClient.OIDCAuthenticate(code, state);
        this.starredTagIds = this.user.starred_tags ?? [];

        // Get the 'next' URL from state
        const state_decoded = JSON.parse(decodeURIComponent(state));
        const nextUrl = state_decoded.next.toString();

        // If there's a 'next' URL, go there, otherwise go to the root
        if (nextUrl) {
            await goto(decodeURIComponent(nextUrl));
        } else {
            await goto("/");
        }
    }

    async logout() {
        await authClient.logout();
        this.user = {
            id: -1,
            username: "",
            role: null,
            starred_tags: [],
        };
        this.starredTagIds = [];
        goto("/users/login");
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
