import { useEffect, useRef } from 'react';
import { useAuth, useUser } from '@clerk/clerk-react';
import { toast } from 'sonner';

/**
 * Hook to display authentication-related toast notifications.
 * Shows welcome messages for new users and handles auth state changes.
 */
export function useAuthToasts() {
  const { isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const hasWelcomedUser = useRef<Set<string>>(new Set());
  const lastAuthState = useRef<boolean | null>(null);

  useEffect(() => {
    if (!isLoaded) return;

    // Detect sign out
    if (lastAuthState.current === true && !isSignedIn) {
      toast.success('Signed out successfully', {
        icon: '👋',
        duration: 3000,
      });
    }

    // Detect sign in
    if (lastAuthState.current === false && isSignedIn && user) {
      const userId = user.id;
      const now = Date.now();
      const userCreatedAt = user.createdAt ? new Date(user.createdAt).getTime() : 0;

      // Check if user was created recently (within last 5 minutes)
      const isNewUser = now - userCreatedAt < 300000; // 5 minutes

      if (isNewUser && !hasWelcomedUser.current.has(userId)) {
        const firstName =
          user.firstName ||
          user.emailAddresses[0]?.emailAddress?.split('@')[0] ||
          'there';

        toast.success(`Welcome to the platform, ${firstName}! 🎉`, {
          duration: 5000,
          description: 'Your account has been created successfully.',
        });

        hasWelcomedUser.current.add(userId);
      } else if (!hasWelcomedUser.current.has(userId)) {
        const firstName =
          user.firstName ||
          user.emailAddresses[0]?.emailAddress?.split('@')[0] ||
          'there';

        toast.success(`Welcome back, ${firstName}!`, {
          icon: '✨',
          duration: 3000,
        });

        hasWelcomedUser.current.add(userId);
      }
    }

    lastAuthState.current = isSignedIn;
  }, [isSignedIn, isLoaded, user]);
}

export default useAuthToasts;