import type { APIRoute } from "astro";
import { launchEnabled } from "../../lib/guard";

export const prerender = false;

/** What this particular deployment allows, so the page can offer only what will work. */
export const GET: APIRoute = async () => Response.json({ launchEnabled });
