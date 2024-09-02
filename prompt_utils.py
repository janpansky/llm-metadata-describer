import logging
from typing import List

logger = logging.getLogger(__name__)


def generate_prompt(data: dict, description_type: str, descriptions_dict: dict, extracted_ids: List[str]) -> str:
    title = data.get('title', '')
    element_id = data.get('id', '')

    context = "\n".join(
        [f"{id_}: {descriptions_dict.get(id_, 'No description available')}" for id_ in extracted_ids])

    # Debugging: Print the context before returning the prompt
    logger.debug(f"Context for {description_type} ID {element_id}: {context}")

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

    elif description_type == "dashboard":
        return (
            f"Generate a descriptive text for a {description_type} with a business meaning "
            f"so I can find it with various similarity search algorithms. "
            f"Do not describe the fields themselves. "
            f"Without any single or double quotes in the beginning and at the end. "
            f"The description must fit within 256 characters based on the following details:\n"
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

    # Confirm that the function is called
    logger.debug("extract_ids_from_visualization_object function called.")
    logger.debug(f"Visualization object content provided: {content}")

    # Access the buckets within the content
    for bucket in content.get('buckets', []):
        logger.debug(f"Processing bucket: {bucket}")
        for item in bucket.get('items', []):
            logger.debug(f"Processing item: {item}")
            measure = item.get('measure', {})
            definition = measure.get('definition', {})
            logger.debug(f"Processing measure definition: {definition}")

            if 'measureDefinition' in definition:
                measure_id = measure['definition']['measureDefinition']['item']['identifier']['id']
                identifiers.append(measure_id)
                logger.debug(f"Found measure ID: {measure_id}")
            elif 'previousPeriodMeasure' in definition:
                for date_dataset in definition['previousPeriodMeasure']['dateDataSets']:
                    dataset_id = date_dataset['dataSet']['identifier']['id']
                    identifiers.append(dataset_id)
                    logger.debug(f"Found dataset ID from previousPeriodMeasure: {dataset_id}")
                measure_identifier = definition['previousPeriodMeasure']['measureIdentifier']
                identifiers.append(measure_identifier)
                logger.debug(f"Found previous period measure ID: {measure_identifier}")

    # Process filters within the content
    for filter_item in content.get('filters', []):
        logger.debug(f"Processing filter item: {filter_item}")
        if 'relativeDateFilter' in filter_item:
            dataset_id = filter_item['relativeDateFilter']['dataSet']['identifier']['id']
            identifiers.append(dataset_id)
            logger.debug(f"Found relative date filter dataset ID: {dataset_id}")

    # Log extracted identifiers
    logger.debug(f"Extracted identifiers from visualization object: {identifiers}")

    # Log descriptions_dict to check the presence of descriptions for these identifiers
    logger.debug(f"Descriptions available for IDs: {list(descriptions_dict.keys())}")

    return identifiers


def extract_ids_from_dashboard(layout: dict, descriptions_dict: dict) -> list:
    identifiers = []

    # Confirm that the function is called
    logger.debug("extract_ids_from_dashboard function called.")
    logger.debug(f"Dashboard layout provided: {layout}")

    for section in layout.get('sections', []):
        logger.debug(f"Processing section: {section}")
        for item in section.get('items', []):
            logger.debug(f"Processing item: {item}")
            widget = item.get('widget', {})
            logger.debug(f"Processing widget: {widget}")

            # Extract insight ID
            insight_id = widget.get('insight', {}).get('identifier', {}).get('id')
            if insight_id:
                identifiers.append(insight_id)
                logger.debug(f"Found insight ID: {insight_id}")

            # Extract drill target IDs
            drills = widget.get('drills', [])
            for drill in drills:
                target_id = drill.get('target', {}).get('identifier', {}).get('id')
                if target_id:
                    identifiers.append(target_id)
                    logger.debug(f"Found drill target ID: {target_id}")

    # Log extracted identifiers
    logger.debug(f"Extracted identifiers from dashboard: {identifiers}")

    # Log descriptions_dict to check the presence of descriptions for these identifiers
    logger.debug(f"Descriptions available for IDs: {list(descriptions_dict.keys())}")

    return identifiers



