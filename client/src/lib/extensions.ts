import BrowserAllOptio from "../extensions/BrowserAllOptio.svelte";
import ImageInfoOptioTable from "../extensions/ImageInfoOptioTable.svelte";
import StudyBlockOptio from "../extensions/StudyBlockOptio.svelte";
import StudyBlockForms from "../extensions/StudyBlockForms.svelte";

export const studyBlockExtensions = [
    {
        component: StudyBlockForms
    },
    {
        component: StudyBlockOptio
    }
]

export const browserExtensions = [
    {
        component: BrowserAllOptio
    }
]

export const imageInfoExtensions = [
    {
        component: ImageInfoOptioTable
    }
]