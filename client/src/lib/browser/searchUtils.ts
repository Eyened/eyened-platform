/**
 * Toggles the value of a parameter in the given URLSearchParams object.
 * If the parameter value is already present, it will be removed. Otherwise, it will be added.
 * Navigates to the new URL.
 * 
 * @param params - The URLSearchParams object to modify.
 * @param variable - The name of the parameter to toggle.
 * @param value - The value of the parameter to toggle.
 */
export function toggleParam(params:URLSearchParams, variable:string, value: string) {

    const values = params.getAll(variable);
    const index = values.indexOf(value);
    if (index >= 0) {
        values.splice(index, 1);
    } else {
        values.push(value);
    }
    params.delete(variable);
    for (const value of values) {
        params.append(variable, value);
    }   
}