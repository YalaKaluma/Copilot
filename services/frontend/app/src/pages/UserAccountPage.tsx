import { UserProfile } from "@clerk/clerk-react";

export function UserAccountPage() {
  return (
    <div className="flex-1 min-h-0 w-full bg-sk-light-grey text-sk-text overflow-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <header>
          <h1 className="text-xl font-semibold text-sk-text">Account</h1>
          <p className="mt-1 text-sm text-sk-contrast-grey">
            Manage your profile and security settings.
          </p>
        </header>
        <div className="mt-6 rounded-2xl border border-gray-200 dark:border-white/10 bg-sk-white p-4">
          <UserProfile
            appearance={{
              elements: {
                card: "shadow-none border-0",
                navbar: "bg-transparent",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
