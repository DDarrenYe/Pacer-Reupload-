import { createClient } from "@supabase/supabase-js";

// The publishable key is meant to be public. Row level security keeps the tables
// closed to it; all data goes through our API.
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
);
