import { goto } from "$app/navigation";
import { resolve } from "$app/paths";
import { page } from "$app/state";
import { authClient, type UserResponse } from "../auth";

export class UserManager {
    public user = $state<UserResponse>({
        id: -1,
        username: "",
        role: null,
        is_admin: false,
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
                    resolve(
                        `/users/login?next=${encodeURIComponent(window.location.href)}`,
                    ),
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

        await goToNext(new URLSearchParams(window.location.search).get("next"));
    }

    async OIDCLogin(code: string, state: string) {
        this.user = await authClient.OIDCAuthenticate(code, state);
        this.starredTagIds = this.user.starred_tags ?? [];

        const state_decoded = JSON.parse(decodeURIComponent(state));
        await goToNext(state_decoded.next.toString());
    }

    async logout() {
        await authClient.logout();
        this.user = {
            id: -1,
            username: "",
            role: null,
            is_admin: false,
            starred_tags: [],
        };
        this.starredTagIds = [];
        goto(resolve("/users/login"));
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

// `next` comes from the URL, so it can name another origin (a mistyped port,
// a stale link) that goto() rejects; go to the root instead.
async function goToNext(next: string | null) {
    const url = next ? URL.parse(next, window.location.origin) : null;
    if (url?.origin === window.location.origin) {
        // eslint-disable-next-line svelte/no-navigation-without-resolve -- redirect target from the URL, not a static route literal
        await goto(url.pathname + url.search + url.hash);
    } else {
        await goto(resolve("/"));
    }
}
