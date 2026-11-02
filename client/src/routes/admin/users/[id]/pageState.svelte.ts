// A reactive stand-in for $app/state's page, so a test can change the route params.
export const page = $state({ params: { id: "3" } });
