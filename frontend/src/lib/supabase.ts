import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabasePublishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

if (!supabaseUrl || !supabasePublishableKey) {
  throw new Error(
    "Supabase env vars missing. Ensure VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY are set."
  );
}

export const supabase = createClient(supabaseUrl, supabasePublishableKey);