import React from 'react';
import ReactDOM from 'react-dom/client';
import { SupportWidget } from './SupportWidget';
import './styles.css';

// Get configuration from script tag
const scriptTag = document.currentScript as HTMLScriptElement | null;
const storeId = scriptTag?.dataset.storeId || 'default';
const apiUrl = scriptTag?.dataset.apiUrl || 'http://localhost:8001';
const position = (scriptTag?.dataset.position || 'bottom-right') as 'bottom-right' | 'bottom-left';

// Create widget container
const container = document.createElement('div');
container.id = 'support-widget-container';
document.body.appendChild(container);

// Render widget
ReactDOM.createRoot(container).render(
  <React.StrictMode>
    <SupportWidget 
      storeId={storeId}
      apiUrl={apiUrl}
      position={position}
    />
  </React.StrictMode>
);
