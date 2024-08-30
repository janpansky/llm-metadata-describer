import logging
from typing import List

logger = logging.getLogger(__name__)

def generate_prompt(data: dict, description_type: str, descriptions_dict: dict, extracted_ids: List[str]) -> str:
    title = data.get('title', '')
    element_id = data.get('id', '')

    if description_type == "metric" or description_type == "non-metric":
        maql = data.get('content', {}).get('maql', '')
        return (
            f"Generate a concise business-relevant description for a {description_type}. This is a metric, "
            f"not a dataset. The description should focus on what the metric measures or calculates "
            f"based on the MAQL (Metric Aggregation Query Language) provided. Do not describe it as a dataset. "
            f"It might be composed of a dataset, but it is operating on top of it. "
            f"Ensure the description highlights the key insights or value this metric provides, "
            f"without technical jargon or irrelevant details. The description should fit within 128 characters.\n"
            f"Title: {title}\n"
            f"ID: {element_id}\n"
            f"MAQL: {maql}\n"
        )

    elif description_type == "visualization object":
        visualization_url = data.get('visualizationUrl', '')
        context = "\n".join(
            [f"{id_}: {descriptions_dict.get(id_, 'No description available')}" for id_ in extracted_ids])

        return (
            f"Generate a descriptive text for a {description_type} with a business meaning "
            f"so I can find it with various similarity search algorithms. "
            f"Do not describe the fields themselves. "
            f"Without any single or double quotes in the beginning and at the end "
            f"Do not mention visualization id. "
            f"The documentation must fit into 128 characters based on the following details:\n"
            f"Title: {title}\n"
            f"ID: {element_id}\n"
            f"Visualization URL: {visualization_url}\n"
            f"Context:\n{context}\n"
        )

    elif description_type == "analytical dashboard":
        context = "\n".join(
            [f"{id_}: {descriptions_dict.get(id_, 'No description available')}" for id_ in extracted_ids])

        return (
            f"Generate a descriptive text for an {description_type} with a business meaning "
            f"so I can find it with various similarity search algorithms. "
            f"Do not describe the fields themselves. "
            f"Without any single or double quotes in the beginning and at the end "
            f"The documentation must fit into 256 characters based on the following details:\n"
            f"Title: {title}\n"
            f"ID: {element_id}\n"
            f"Context:\n{context}\n"
        )

    else:
        return (
            f"Generate a descriptive text with business meaning for a {description_type}. "
            f"Do not describe the fields themselves. "
            f"Without any single or double quotes in the beginning and at the end. "
            f"The documentation must fit into 128 characters based on the following details:\n"
            f"Title: {title}\n"
            f"ID: {element_id}\n"
        )


def extract_ids_from_visualization_object(content: dict, descriptions_dict: dict) -> list:
    identifiers = []
    for bucket in content.get('buckets', []):
        for item in bucket.get('items', []):
            measure = item.get('measure', {})
            definition = measure.get('definition', {})
            if 'measureDefinition' in definition:
                identifiers.append(measure['definition']['measureDefinition']['item']['identifier']['id'])
            elif 'previousPeriodMeasure' in definition:
                for date_dataset in definition['previousPeriodMeasure']['dateDataSets']:
                    identifiers.append(date_dataset['dataSet']['identifier']['id'])
                identifiers.append(definition['previousPeriodMeasure']['measureIdentifier'])

    for filter_item in content.get('filters', []):
        if 'relativeDateFilter' in filter_item:
            identifiers.append(filter_item['relativeDateFilter']['dataSet']['identifier']['id'])

    return identifiers


def extract_ids_from_dashboard(layout: dict, descriptions_dict: dict) -> list:
    identifiers = []
    for section in layout.get('sections', []):
        for item in section.get('items', []):
            widget = item.get('widget', {})
            insight = widget.get('insight', {})
            if 'identifier' in insight:
                identifiers.append(insight['identifier']['id'])

    return identifiers
