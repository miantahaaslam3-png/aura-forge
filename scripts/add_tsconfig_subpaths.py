import json

p = 'apps/desktop/tsconfig.json'
d = json.load(open(p))
paths = d['compilerOptions']['paths']
paths['@auraforge/shared/billing-policy'] = ['../auraforge-shared/src/billing-policy.ts']
paths['@auraforge/shared/charge-settlement'] = ['../auraforge-shared/src/charge-settlement.ts']
json.dump(d, open(p, 'w'), indent=2)
open(p, 'a').write('\n')
print('added subpaths to tsconfig')