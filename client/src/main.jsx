import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
import Dashboard from "./Dashboard.jsx";
import ItemView from "./ItemView.jsx";
import Review from "./Review.jsx";
import "highlight.js/styles/github.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/item/:id" element={<ItemView />} />
          <Route path="/study" element={<Review />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
