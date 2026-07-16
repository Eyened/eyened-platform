/**
 * Legacy fallback for non-secure contexts (e.g. HTTP on a LAN hostname).
 * execCommand is deprecated but remains the only widely supported alternative
 * when navigator.clipboard is unavailable.
 */
function copyViaExecCommand(text: string): boolean {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "0";
    textarea.style.left = "0";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    return copied;
}

export async function copyToClipboard(text: string): Promise<boolean> {
    const value = String(text);

    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(value);
            return true;
        } catch {
            // Fall through to execCommand below.
        }
    }

    return copyViaExecCommand(value);
}
