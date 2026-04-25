export type StoreKey =
  | "fravega"
  | "megatone"
  | "cetrogar"
  | "castillo"
  | "oncity"
  | "monteshermanos";

export interface StoreMeta {
  key: StoreKey;
  displayName: string;
  color: string;
  regional: boolean;
}

export const STORES: readonly StoreMeta[] = [
  { key: "fravega",        displayName: "Fravega",         color: "hsl(262, 52%, 47%)", regional: false },
  { key: "megatone",       displayName: "Megatone",        color: "hsl(200, 50%, 45%)", regional: false },
  { key: "cetrogar",       displayName: "Cetrogar",        color: "hsl(355, 65%, 50%)", regional: false },
  { key: "oncity",         displayName: "OnCity",          color: "hsl(32, 80%, 52%)",  regional: false },
  { key: "monteshermanos", displayName: "Montes Hermanos", color: "hsl(320, 50%, 48%)", regional: false },
  { key: "castillo",       displayName: "Castillo",        color: "hsl(142, 45%, 40%)", regional: true },
] as const;

export const STORE_KEYS: readonly StoreKey[] = STORES.map((s) => s.key);

const STORE_BY_KEY: Record<StoreKey, StoreMeta> = STORES.reduce(
  (acc, store) => {
    acc[store.key] = store;
    return acc;
  },
  {} as Record<StoreKey, StoreMeta>,
);

export function getStore(key: string): StoreMeta | undefined {
  return STORE_BY_KEY[key as StoreKey];
}

export function getStoreDisplayName(key: string): string {
  return STORE_BY_KEY[key as StoreKey]?.displayName ?? key;
}

export function getStoreColor(key: string): string {
  return STORE_BY_KEY[key as StoreKey]?.color ?? "hsl(262, 52%, 47%)";
}

export function isKnownStoreKey(key: string): key is StoreKey {
  return key in STORE_BY_KEY;
}
