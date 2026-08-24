import { fetchApi } from '$lib/api/client';

export type DataRow = (number | string | null)[];
export type DataSource = Record<string, DataRow[]>;

const cache = new Map<string, Promise<DataSource>>();

function isAbsoluteUrl(url: string): boolean {
	return /^https?:\/\//i.test(url);
}

export async function loadDataSource(
	url: string,
	cached: boolean = true
): Promise<DataSource> {
	if (cached && cache.has(url)) {
		return cache.get(url)!;
	}

	const request = async (): Promise<DataSource> => {
		const response = isAbsoluteUrl(url)
			? await fetch(url)
			: await fetchApi(url);

		if (!response.ok) {
			throw new Error(`Failed to load data source from ${url}`);
		}

		return response.json();
	};

	const promise = request();

	if (cached) {
		cache.set(url, promise);
	}

	return promise;
}

/**
 * Resolves a template URL with the given context.
 *
 * @param template url with placeholders e.g. ${patient.identifier} or ${patient.identifier:defaultValue}
 * @param context object with the data to be substituted
 * @returns the resolved URL
 */
export function resolveURL(template: string, context: any): string {
	return template.replace(
		/\$\{([^}:]+(?:\.[^}:]+)*)(?::([^}]*))?\}/g,
		(_, key, defaultValue) => {
			try {
				const value = resolveValue(key, context);
				if (value instanceof Date) {
					return (
						value.getFullYear() +
						'-' +
						(value.getMonth() + 1) +
						'-' +
						value.getDate()
					);
				}
				// Handle datetime strings (ISO format like "2024-01-15T10:30:00" or "2024-01-15")
				if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
					return value.split('T')[0]; // Extract just the date part (YYYY-MM-DD)
				}
				return String(value);
			} catch (error) {
				console.error(`Failed to resolve ${key}:`, error);
				return defaultValue ?? '';
			}
		}
	);
}

export function resolveValue(key: string, context: any): any {
	const path = key.split('.');
	let value = context;
	for (const p of path) {
		if (value == null || !(p in value)) {
			return null;
		}
		value = value[p];
	}
	return value;
}

