export interface SouthAfricanCity {
  id: string
  name: string
  province: string
  submarkets: readonly string[]
}

export interface SouthAfricanSubmarket {
  id: string
  name: string
  market: string
  marketId: string
  province: string
}

// Maintainable V1 market list. City and province names are curated from the
// South African Government's province and local-government directories.
// Commercial submarkets are intentionally limited to known prepared values. An
// empty list means no market-specific suggestions are available yet.
export const southAfricanCities: readonly SouthAfricanCity[] = [
  {
    id: 'johannesburg',
    name: 'Johannesburg',
    province: 'Gauteng',
    submarkets: [
      'Johannesburg CBD',
      'Sandton',
      'Rosebank',
      'Bryanston',
      'Fourways',
      'Randburg',
      'Midrand',
      'Waterfall',
      'Melrose Arch',
      'Illovo',
      'Rivonia',
      'Woodmead',
      'Sunninghill',
    ],
  },
  {
    id: 'pretoria',
    name: 'Pretoria',
    province: 'Gauteng',
    submarkets: [
      'Pretoria CBD',
      'Menlyn',
      'Hatfield',
      'Centurion',
      'Brooklyn',
      'Lynnwood',
      'Montana',
      'Highveld Technopark',
      'Irene',
    ],
  },
  {
    id: 'ekurhuleni',
    name: 'Ekurhuleni',
    province: 'Gauteng',
    submarkets: [
      'Bedfordview',
      'Edenvale',
      'Germiston',
      'Boksburg',
      'Benoni',
      'Kempton Park',
      'Isando',
      'Longmeadow',
    ],
  },
  {
    id: 'vanderbijlpark',
    name: 'Vanderbijlpark',
    province: 'Gauteng',
    submarkets: [],
  },
  {
    id: 'vereeniging',
    name: 'Vereeniging',
    province: 'Gauteng',
    submarkets: [],
  },
  {
    id: 'krugersdorp',
    name: 'Krugersdorp',
    province: 'Gauteng',
    submarkets: [],
  },

  {
    id: 'cape-town',
    name: 'Cape Town',
    province: 'Western Cape',
    submarkets: [
      'Cape Town CBD',
      'Century City',
      'Claremont',
      'Bellville',
      'Woodstock',
      'V&A Waterfront',
      'Foreshore',
      'Paarden Eiland',
      'Epping',
      'Montague Gardens',
      'Brackenfell',
    ],
  },
  {
    id: 'stellenbosch',
    name: 'Stellenbosch',
    province: 'Western Cape',
    submarkets: [],
  },
  { id: 'paarl', name: 'Paarl', province: 'Western Cape', submarkets: [] },
  { id: 'george', name: 'George', province: 'Western Cape', submarkets: [] },
  {
    id: 'mossel-bay',
    name: 'Mossel Bay',
    province: 'Western Cape',
    submarkets: [],
  },
  {
    id: 'worcester',
    name: 'Worcester',
    province: 'Western Cape',
    submarkets: [],
  },
  { id: 'knysna', name: 'Knysna', province: 'Western Cape', submarkets: [] },
  {
    id: 'somerset-west',
    name: 'Somerset West',
    province: 'Western Cape',
    submarkets: [],
  },

  {
    id: 'durban',
    name: 'Durban',
    province: 'KwaZulu-Natal',
    submarkets: [
      'Durban CBD',
      'Umhlanga',
      'La Lucia',
      'Westville',
      'Pinetown',
      'Riverhorse Valley',
      'Springfield',
      'Mount Edgecombe',
    ],
  },
  {
    id: 'pietermaritzburg',
    name: 'Pietermaritzburg',
    province: 'KwaZulu-Natal',
    submarkets: [],
  },
  {
    id: 'richards-bay',
    name: 'Richards Bay',
    province: 'KwaZulu-Natal',
    submarkets: [],
  },
  { id: 'ballito', name: 'Ballito', province: 'KwaZulu-Natal', submarkets: [] },
  {
    id: 'newcastle',
    name: 'Newcastle',
    province: 'KwaZulu-Natal',
    submarkets: [],
  },
  {
    id: 'ladysmith',
    name: 'Ladysmith',
    province: 'KwaZulu-Natal',
    submarkets: [],
  },

  {
    id: 'gqeberha',
    name: 'Gqeberha',
    province: 'Eastern Cape',
    submarkets: [
      'Central',
      'Newton Park',
      'Walmer',
      'Greenacres',
      'Korsten',
      'Coega',
    ],
  },
  {
    id: 'east-london',
    name: 'East London',
    province: 'Eastern Cape',
    submarkets: [
      'East London CBD',
      'Vincent',
      'Beacon Bay',
      'Berea',
      'Arcadia',
      'West Bank',
    ],
  },
  { id: 'mthatha', name: 'Mthatha', province: 'Eastern Cape', submarkets: [] },
  { id: 'bhisho', name: 'Bhisho', province: 'Eastern Cape', submarkets: [] },
  {
    id: 'makhanda',
    name: 'Makhanda',
    province: 'Eastern Cape',
    submarkets: [],
  },

  {
    id: 'bloemfontein',
    name: 'Bloemfontein',
    province: 'Free State',
    submarkets: [
      'Bloemfontein CBD',
      'Westdene',
      'Brandwag',
      'Langenhoven Park',
      'Hamilton',
    ],
  },
  { id: 'welkom', name: 'Welkom', province: 'Free State', submarkets: [] },
  {
    id: 'bethlehem',
    name: 'Bethlehem',
    province: 'Free State',
    submarkets: [],
  },
  {
    id: 'sasolburg',
    name: 'Sasolburg',
    province: 'Free State',
    submarkets: [],
  },
  {
    id: 'kroonstad',
    name: 'Kroonstad',
    province: 'Free State',
    submarkets: [],
  },

  {
    id: 'polokwane',
    name: 'Polokwane',
    province: 'Limpopo',
    submarkets: ['Polokwane CBD', 'Bendor', 'Magna Via', 'Laboria'],
  },
  { id: 'tzaneen', name: 'Tzaneen', province: 'Limpopo', submarkets: [] },
  {
    id: 'thohoyandou',
    name: 'Thohoyandou',
    province: 'Limpopo',
    submarkets: [],
  },
  { id: 'mokopane', name: 'Mokopane', province: 'Limpopo', submarkets: [] },
  { id: 'lephalale', name: 'Lephalale', province: 'Limpopo', submarkets: [] },
  { id: 'musina', name: 'Musina', province: 'Limpopo', submarkets: [] },

  {
    id: 'mbombela',
    name: 'Mbombela',
    province: 'Mpumalanga',
    submarkets: ['Mbombela CBD', 'Riverside', 'West Acres'],
  },
  {
    id: 'emalahleni',
    name: 'eMalahleni',
    province: 'Mpumalanga',
    submarkets: [],
  },
  {
    id: 'middelburg',
    name: 'Middelburg',
    province: 'Mpumalanga',
    submarkets: [],
  },
  { id: 'secunda', name: 'Secunda', province: 'Mpumalanga', submarkets: [] },
  { id: 'ermelo', name: 'Ermelo', province: 'Mpumalanga', submarkets: [] },
  {
    id: 'white-river',
    name: 'White River',
    province: 'Mpumalanga',
    submarkets: [],
  },

  {
    id: 'rustenburg',
    name: 'Rustenburg',
    province: 'North West',
    submarkets: ['Rustenburg CBD', 'Waterfall East', 'Zinniaville'],
  },
  { id: 'mahikeng', name: 'Mahikeng', province: 'North West', submarkets: [] },
  {
    id: 'potchefstroom',
    name: 'Potchefstroom',
    province: 'North West',
    submarkets: [],
  },
  {
    id: 'klerksdorp',
    name: 'Klerksdorp',
    province: 'North West',
    submarkets: [],
  },
  { id: 'brits', name: 'Brits', province: 'North West', submarkets: [] },

  {
    id: 'kimberley',
    name: 'Kimberley',
    province: 'Northern Cape',
    submarkets: ['Kimberley CBD', 'Monument Heights', 'Royldene'],
  },
  {
    id: 'upington',
    name: 'Upington',
    province: 'Northern Cape',
    submarkets: [],
  },
  { id: 'kathu', name: 'Kathu', province: 'Northern Cape', submarkets: [] },
] as const

export function filterSouthAfricanCities(query: string): SouthAfricanCity[] {
  const term = query.trim().toLocaleLowerCase('en-ZA')
  if (!term) return [...southAfricanCities]
  return southAfricanCities.filter(({ name, province }) =>
    `${name} ${province}`.toLocaleLowerCase('en-ZA').includes(term),
  )
}

export function findSouthAfricanCity(
  name: string,
): SouthAfricanCity | undefined {
  const normalized = name.trim().toLocaleLowerCase('en-ZA')
  return southAfricanCities.find(
    (city) => city.name.toLocaleLowerCase('en-ZA') === normalized,
  )
}

export function submarketsForCity(cityName: string): string[] {
  return [...(findSouthAfricanCity(cityName)?.submarkets ?? [])]
}

export const southAfricanSubmarkets: readonly SouthAfricanSubmarket[] =
  southAfricanCities.flatMap((city) =>
    city.submarkets.map((name) => ({
      id: `${city.id}:${name.toLocaleLowerCase('en-ZA').replaceAll(/[^a-z0-9]+/g, '-')}`,
      name,
      market: city.name,
      marketId: city.id,
      province: city.province,
    })),
  )

const preparedSubmarketNames = new Set(
  southAfricanSubmarkets.map(({ name }) => name),
)

export function addPreparedSubmarket(
  selected: readonly string[],
  value: string,
): string[] {
  if (!preparedSubmarketNames.has(value) || selected.includes(value))
    return [...selected]
  return [...selected, value]
}

export function removeSelectedSubmarket(
  selected: readonly string[],
  value: string,
): string[] {
  return selected.filter((item) => item !== value)
}

export function filterSouthAfricanSubmarkets(
  query: string,
  primaryMarket: string,
  selected: readonly string[] = [],
): SouthAfricanSubmarket[] {
  const term = query.trim().toLocaleLowerCase('en-ZA')
  const selectedNames = new Set(
    selected.map((value) => value.toLocaleLowerCase('en-ZA')),
  )
  const available = southAfricanSubmarkets.filter(
    ({ name }) => !selectedNames.has(name.toLocaleLowerCase('en-ZA')),
  )

  if (!term) return available.filter(({ market }) => market === primaryMarket)

  return available
    .filter(({ name, market, province }) =>
      `${name} ${market} ${province}`.toLocaleLowerCase('en-ZA').includes(term),
    )
    .sort((left, right) => {
      const marketDifference =
        Number(right.market === primaryMarket) -
        Number(left.market === primaryMarket)
      return marketDifference || left.name.localeCompare(right.name, 'en-ZA')
    })
}
