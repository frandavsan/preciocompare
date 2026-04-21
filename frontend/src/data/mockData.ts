export type Product = {
  id: string;
  name: string;
  category: string;
  imageUrl: string;
  prices: StorePrice[];
  priceHistory: PricePoint[];
};

export type StorePrice = {
  store: string;
  price: number;
  currency: string;
  url: string;
  inStock: boolean;
  freeShipping: boolean;
};

export type PricePoint = {
  date: string;
  store: string;
  price: number;
};

export const stores = [
  { name: "Mercado Libre", color: "hsl(36, 80%, 56%)" },
  { name: "Fravega", color: "hsl(262, 52%, 47%)" },
  { name: "Garbarino", color: "hsl(170, 45%, 42%)" },
  { name: "Musimundo", color: "hsl(340, 55%, 50%)" },
  { name: "Megatone", color: "hsl(200, 50%, 45%)" },
];

export const categories = [
  "Celulares",
  "Notebooks",
  "Televisores",
  "Audio",
  "Tablets",
  "Consolas",
];

const generateHistory = (basePrice: number, storeName: string): PricePoint[] => {
  const points: PricePoint[] = [];
  const months = ["Sep", "Oct", "Nov", "Dic", "Ene", "Feb", "Mar"];
  let price = basePrice;
  for (const month of months) {
    price = price + (Math.random() - 0.4) * basePrice * 0.08;
    points.push({ date: month, store: storeName, price: Math.round(price) });
  }
  return points;
};

export const products: Product[] = [
  {
    id: "1",
    name: "Samsung Galaxy S24 Ultra 256GB",
    category: "Celulares",
    imageUrl: "https://images.samsung.com/us/smartphones/galaxy-s24-ultra/images/galaxy-s24-ultra-share-image.jpg",
    prices: [
      { store: "Mercado Libre", price: 1849999, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Fravega", price: 1929000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Garbarino", price: 1999990, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Musimundo", price: 1879900, currency: "ARS", url: "#", inStock: false, freeShipping: true },
      { store: "Megatone", price: 1959000, currency: "ARS", url: "#", inStock: true, freeShipping: false },
    ],
    priceHistory: [
      ...generateHistory(1850000, "Mercado Libre"),
      ...generateHistory(1930000, "Fravega"),
      ...generateHistory(2000000, "Garbarino"),
    ],
  },
  {
    id: "2",
    name: "MacBook Air M3 15\" 256GB",
    category: "Notebooks",
    imageUrl: "https://www.apple.com/v/macbook-air/z/images/meta/macbook_air_mx__ez5y0k5yy7au_og.png?202603261117",
    prices: [
      { store: "Mercado Libre", price: 2499000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Fravega", price: 2650000, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Garbarino", price: 2589990, currency: "ARS", url: "#", inStock: false, freeShipping: false },
      { store: "Musimundo", price: 2549900, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Megatone", price: 2619000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
    ],
    priceHistory: [
      ...generateHistory(2500000, "Mercado Libre"),
      ...generateHistory(2650000, "Fravega"),
      ...generateHistory(2590000, "Garbarino"),
    ],
  },
  {
    id: "3",
    name: "Sony PlayStation 5 Slim Digital",
    category: "Consolas",
    imageUrl: "https://gmedia.playstation.com/is/image/SIEPDC/ps5-product-thumbnail-01-en-14sep21?$facebook$",
    prices: [
      { store: "Mercado Libre", price: 899999, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Fravega", price: 949000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Garbarino", price: 979990, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Musimundo", price: 929900, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Megatone", price: 959000, currency: "ARS", url: "#", inStock: false, freeShipping: false },
    ],
    priceHistory: [
      ...generateHistory(900000, "Mercado Libre"),
      ...generateHistory(950000, "Fravega"),
      ...generateHistory(980000, "Garbarino"),
    ],
  },
  {
    id: "4",
    name: "Samsung Smart TV 65\" 4K Neo QLED",
    category: "Televisores",
    imageUrl: "https://image-us.samsung.com/SamsungUS/home/television-home-theater/tvs/neoqled-4k/02072024/QN75QN90DAFXZA_006_Front2_GraphiteBlack_1600x1200.jpg",
    prices: [
      { store: "Mercado Libre", price: 1299000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Fravega", price: 1389000, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Garbarino", price: 1349990, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Musimundo", price: 1419900, currency: "ARS", url: "#", inStock: false, freeShipping: true },
      { store: "Megatone", price: 1379000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
    ],
    priceHistory: [
      ...generateHistory(1300000, "Mercado Libre"),
      ...generateHistory(1390000, "Fravega"),
      ...generateHistory(1350000, "Garbarino"),
    ],
  },
  {
    id: "5",
    name: "Apple AirPods Pro 2da Gen USB-C",
    category: "Audio",
    imageUrl: "https://www.apple.com/v/airpods-pro/r/images/meta/og__c0ceegchesom_overview.png?202603242312",
    prices: [
      { store: "Mercado Libre", price: 449999, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Fravega", price: 489000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Garbarino", price: 469990, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Musimundo", price: 459900, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Megatone", price: 479000, currency: "ARS", url: "#", inStock: true, freeShipping: false },
    ],
    priceHistory: [
      ...generateHistory(450000, "Mercado Libre"),
      ...generateHistory(490000, "Fravega"),
      ...generateHistory(470000, "Garbarino"),
    ],
  },
  {
    id: "6",
    name: "iPad Air M2 11\" 128GB WiFi",
    category: "Tablets",
    imageUrl: "https://www.apple.com/v/ipad-air/ah/images/meta/ipad-air_overview__bc2fd15uec0y_og.png?202603101707",
    prices: [
      { store: "Mercado Libre", price: 1199000, currency: "ARS", url: "#", inStock: false, freeShipping: true },
      { store: "Fravega", price: 1279000, currency: "ARS", url: "#", inStock: false, freeShipping: false },
      { store: "Garbarino", price: 1249990, currency: "ARS", url: "#", inStock: true, freeShipping: false },
      { store: "Musimundo", price: 1259900, currency: "ARS", url: "#", inStock: true, freeShipping: true },
      { store: "Megatone", price: 1289000, currency: "ARS", url: "#", inStock: true, freeShipping: true },
    ],
    priceHistory: [
      ...generateHistory(1200000, "Mercado Libre"),
      ...generateHistory(1280000, "Fravega"),
      ...generateHistory(1250000, "Garbarino"),
    ],
  },
];

export const formatPrice = (price: number): string => {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(price);
};
