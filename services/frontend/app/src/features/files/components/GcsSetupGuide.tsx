import { Cloud, AlertCircle } from 'lucide-react';

interface GcsSetupGuideProps {
  onRetryCheck: () => void;
}

export function GcsSetupGuide({ onRetryCheck }: GcsSetupGuideProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-8 py-6">
            <div className="flex items-center space-x-3">
              <Cloud className="h-8 w-8 text-white" />
              <div>
                <h1 className="text-2xl font-bold text-white">Google Cloud Storage Setup Required</h1>
                <p className="text-blue-100 mt-1">Configure your GCS bucket to enable file uploads</p>
              </div>
            </div>
          </div>
          
          <div className="px-8 py-6">
            <div className="space-y-6">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="font-medium text-amber-900">No GCS Bucket Configured</h3>
                    <p className="text-sm text-amber-800 mt-1">
                      File storage requires a Google Cloud Storage bucket to be configured in your environment variables.
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Setup Instructions</h2>
                <div className="space-y-4">
                  <SetupStep
                    step={1}
                    title="Configure Environment Variables"
                    description="Add these to your backend .env file:"
                  >
                    <div className="mt-2 bg-gray-900 text-gray-100 p-3 rounded text-xs font-mono">
                      <div className="text-green-400"># Google Cloud Storage</div>
                      <div>GCS_BUCKET_NAME=your-bucket-name</div>
                      <div>GCP_PROJECT_ID=your-project-id</div>
                      <div>GOOGLE_SERVICE_ACCOUNT_JSON='{"{"}"type":"service_account",...{"}"}'</div>
                    </div>
                  </SetupStep>
                  
                  <SetupStep
                    step={2}
                    title="Create GCS Bucket"
                    description={
                      <>
                        Create a bucket in the{' '}
                        <a 
                          href="https://console.cloud.google.com/storage" 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="text-blue-600 hover:underline"
                        >
                          Google Cloud Console
                        </a>{' '}
                        and copy its name to your <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">GCS_BUCKET_NAME</code>
                      </>
                    }
                  />
                  
                  <SetupStep
                    step={3}
                    title="Restart Backend"
                    description="Restart your backend server:"
                  >
                    <code className="block mt-1 bg-gray-100 px-2 py-1 rounded text-xs">
                      docker-compose restart backend
                    </code>
                  </SetupStep>
                </div>
              </div>
              
              <div className="border-t pt-6">
                <button
                  onClick={onRetryCheck}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors text-sm font-medium"
                >
                  Check Configuration Again
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface SetupStepProps {
  step: number;
  title: string;
  description: React.ReactNode;
  children?: React.ReactNode;
}

function SetupStep({ step, title, description, children }: SetupStepProps) {
  return (
    <div className="flex items-start space-x-3">
      <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold text-sm">
        {step}
      </span>
      <div>
        <h4 className="font-medium text-gray-900">{title}</h4>
        <p className="text-sm text-gray-600 mt-1">{description}</p>
        {children}
      </div>
    </div>
  );
}