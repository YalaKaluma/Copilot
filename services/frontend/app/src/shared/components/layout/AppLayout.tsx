import { ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import AppHeader from "./AppHeader";

interface AppLayoutProps {
  children?: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const location = useLocation();
  const isChatRoute = location.pathname.startsWith("/chat");

  return (
    <div className="h-screen flex flex-col bg-sk-white overflow-hidden">
      {!isChatRoute && <AppHeader />}
      <main
        className={
          isChatRoute
            ? "flex-1 min-h-0 flex flex-col"
            : "flex-1 min-h-0 bg-sk-white"
        }
      >
        {children || <Outlet />}
      </main>
    </div>
  );
}
