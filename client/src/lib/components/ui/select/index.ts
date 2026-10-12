import { Select as SelectPrimitive } from "bits-ui";

import Content from "./select-content.svelte";
import Item from "./select-item.svelte";
import Trigger from "./select-trigger.svelte";

const Root = SelectPrimitive.Root;

export {
    Content,
    Item,
    Root,
    Trigger,
    //
    Root as Select,
    Content as SelectContent,
    Item as SelectItem,
    Trigger as SelectTrigger,
};
