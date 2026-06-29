/** Builtin viewer FormSchema names — keep in sync with orm/eyened_orm/form_schemas/registry.py */
export const BUILTIN_VIEWER_FORM_SCHEMA_NAMES = {
	ETDRS_GRID: 'ETDRS-grid coordinates',
	POINTSET_REGISTRATION: 'Pointset registration',
	AFFINE_REGISTRATION: 'Affine registration',
	REGISTRATION_SET: 'RegistrationSet',
} as const;

export type BuiltinViewerFormSchemaName =
	(typeof BUILTIN_VIEWER_FORM_SCHEMA_NAMES)[keyof typeof BUILTIN_VIEWER_FORM_SCHEMA_NAMES];

export const HIDE_FROM_FORM_PANEL_NAMES = new Set<string>(
	Object.values(BUILTIN_VIEWER_FORM_SCHEMA_NAMES),
);
