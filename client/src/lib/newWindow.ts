import type { Component } from 'svelte';

import { mount, unmount } from 'svelte';

export function openNewWindow(Component: Component, props: any, title: string): Window | null {
	const screenWidth = window.screen.availWidth;
	const screenHeight = window.screen.availHeight;
	const width = 0.5 * screenWidth; // 50% of screen width
	const height = 0.8 * screenHeight; // 80% of screen height
	const left = (screenWidth - width) / 2;
	const top = (screenHeight - height) / 2;

	const windowFeatures = [
		`width=${width}`,
		`height=${height}`,
		`left=${left}`,
		`top=${top}`,
		'resizable=yes',
		'scrollbars=yes',
		'toolbar=no',
		'menubar=no',
		'status=no',
		'location=no'
	].join(',');

	const newWin = window.open('', '_blank', windowFeatures);

	if (newWin) {
		newWin.document.title = title;

		// Add CSS to the new window
		// Inject the same CSS styles used in the main window
		document.querySelectorAll("link[rel='stylesheet'], style").forEach((styleNode) => {
			const newStyle = newWin.document.createElement(styleNode.tagName);
			if (styleNode.tagName.toLowerCase() === 'link') {
				// Clone <link> elements (stylesheets)
				newStyle.href = (styleNode as HTMLLinkElement).href;
				newStyle.rel = 'stylesheet';
			} else {
				// Clone <style> elements (internal styles)
				newStyle.innerHTML = (styleNode as HTMLStyleElement).innerHTML;
			}
			newWin.document.head.appendChild(newStyle);
		});

		const app = mount(Component, {
			target: newWin.document.body,
			props
		});

		// Cleanup when the window is closed
		newWin.addEventListener('beforeunload', () => {
			unmount(app);
		});
	} else {
		alert('Popup blocked! Please allow popups for this site.');
		
	}
	
	return newWin;
}
