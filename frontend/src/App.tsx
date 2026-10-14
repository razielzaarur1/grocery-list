import React, { useState } from 'react';
import { GroceryList } from './components/GroceryList';
import { PinLockScreen } from './components/PinLockScreen';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-[#f6f8f6]">
      {!isAuthenticated ? (
        <PinLockScreen onSuccess={() => setIsAuthenticated(true)} />
      ) : (
        <GroceryList />
      )}
    </div>
  );
}

export default App;
