import { ShowcaseHeader } from '../shared/components/showcase/ShowcaseHeader';
import { ShowcaseComponentCard } from '../shared/components/showcase/ShowcaseComponentCard';
import { showcaseComponents } from '../shared/data/showcaseComponents';

export function ComponentShowcasePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-white">
      <ShowcaseHeader />
      
      <div className="max-w-7xl mx-auto px-8 py-12">
        <div className="grid lg:grid-cols-2 gap-8">
          {showcaseComponents.map((component, index) => (
            <ShowcaseComponentCard
              key={component.id}
              {...component}
              index={index}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default ComponentShowcasePage;