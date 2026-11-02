// Pages a logged-out visitor may open without being sent to the login page.
const PUBLIC_PATHS = ["/users/login", "/users/signup", "/users/oidc-callback"];

export function isPublicPath(pathname: string): boolean {
    return PUBLIC_PATHS.some((path) => pathname.startsWith(path));
}
