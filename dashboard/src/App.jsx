import React, { useEffect, useState } from "react";
import Surface from "./pages/Surface.jsx";
import Submit from "./pages/Submit.jsx";
import Queue from "./pages/Queue.jsx";
import Job from "./pages/Job.jsx";
import Savings from "./pages/Savings.jsx";
import Quality from "./pages/Quality.jsx";

const PAGES = [
  ["submit", "Submit"], ["queue", "Queue"], ["surface", "Surface"],
  ["savings", "Savings"], ["quality", "Forecast quality"],
];

function useRoute() {
  const read = () => (window.location.hash.replace(/^#\/?/, "") || "submit").split("/");
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export default function App() {
  const [page, arg] = useRoute();
  let body;
  if (page === "jobs" && arg) body = <Job id={decodeURIComponent(arg)} />;
  else if (page === "queue") body = <Queue />;
  else if (page === "surface") body = <Surface />;
  else if (page === "savings") body = <Savings />;
  else if (page === "quality") body = <Quality />;
  else body = <Submit />;
  return (
    <>
      <header className="top">
        <a className="brand" href="#/submit">Pravaah<small>water- and carbon-aware AI scheduling</small></a>
        <nav>
          {PAGES.map(([id, label]) => (
            <a key={id} href={`#/${id}`} className={page === id || (page === "jobs" && id === "queue") ? "on" : ""}>{label}</a>
          ))}
        </nav>
      </header>
      <main>{body}</main>
    </>
  );
}
