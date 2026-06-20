import { useAuth, SignIn } from '@clerk/clerk-react';
import { ReactNode } from 'react';
import { Outlet } from 'react-router-dom';

interface ProtectedRouteProps {
  children?: ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return <div className="h-screen bg-sk-white" />;
  }

  if (!isSignedIn) {
    return (
      <div className="h-screen bg-sk-white flex items-center justify-center">
        <SignIn />
      </div>
    );
  }

  return children || <Outlet />;
}