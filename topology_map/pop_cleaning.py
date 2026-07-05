from collections import defaultdict

def collapse_pops(virtual_pops, countries_with_regions):
    """
    Collapse multiple PoPs per AS when only country-level emissions are available.

    Parameters
    ----------
    virtual_pops : list of dicts
    countries_with_regions : set of country codes with region-level emissions

    Returns
    -------
    cleaned_pops : list of dicts
    """
    grouped = defaultdict(list)

    for entry in virtual_pops:
        asn = entry["as_number"]
        country = entry["country"]

        # Keep full region info only if we have region-level emissions
        if country in countries_with_regions:
            key = (asn, country, entry["region"])
        else:
            key = (asn, country)

        grouped[key].append(entry)

    cleaned_pops = []
    for key, entries in grouped.items():
        if len(entries) == 1:
            cleaned_pops.append(entries[0])
        else:
            # collapse: pick one representative PoP (the first one)
            rep = entries[0].copy()
            rep["pop"] = f"{rep['as_number']}-{rep['country']}"
            rep["region"] = ""   # collapsed, so no region
            cleaned_pops.append(rep)

    return cleaned_pops
