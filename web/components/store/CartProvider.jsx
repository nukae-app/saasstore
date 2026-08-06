'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';

const CartContext = createContext({ items: [], total: '0.00', itemCount: 0, refresh: async () => {} });

export function useCart() {
  return useContext(CartContext);
}

export default function CartProvider({ children }) {
  const [cart, setCart] = useState({ items: [], total: '0.00' });

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/cart', { credentials: 'include' });
      if (res.ok) setCart(await res.json());
    } catch {}
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const itemCount = cart.items.reduce((sum, i) => sum + (i.cantidad || 1), 0);

  return (
    <CartContext.Provider value={{ ...cart, itemCount, refresh }}>
      {children}
    </CartContext.Provider>
  );
}
