import tiktoken
import json
import re
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network
from IPython.display import IFrame, display, HTML
import os
from groq import Groq

def count_tokens(text, model="cl100k_base"):
    """Count the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(model)
    return len(encoding.encode(text))

def extract_json_from_llm_output(llm_output):
    """
    Extract valid JSON from LLM output, filtering out thinking sections and other text.
    
    Args:
        llm_output (str): The raw output from the LLM
        
    Returns:
        dict: The parsed JSON object
    """
    # Try to find JSON enclosed in triple backticks
    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    matches = re.findall(json_pattern, llm_output)
    
    if matches:
        # Take the last match if multiple exist
        json_str = matches[-1].strip()
    else:
        # If no backticks found, try to find JSON directly
        json_pattern = r'(\{[\s\S]*\})'
        matches = re.findall(json_pattern, llm_output)
        if matches:
            json_str = matches[-1].strip()
        else:
            raise ValueError("No JSON found in the output")
    
    try:
        # Parse the JSON to ensure it's valid
        json_data = json.loads(json_str)
        return json_data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON found: {e}")

def parse_entity_data(json_data):
    """Parse entity data from JSON string or dictionary"""
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string")
    else:
        data = json_data
    return data

def create_graph(data):
    """Create NetworkX graph from entity data"""
    G = nx.DiGraph()
    
    # Add nodes
    for node in data.get('nodes', []):
        # Collect attributes
        attrs = {
            'name': node.get('name', ''),
            'type': node.get('type', ''),
            'label': node.get('name', '')
        }
        
        # Add quote if available
        if 'quote' in node:
            attrs['quote'] = node['quote']
        
        # Add any additional attributes
        if 'attributes' in node:
            attrs['attributes'] = node['attributes']
        
        G.add_node(node['id'], **attrs)
    
    # Add edges
    for edge in data.get('edges', []):
        edge_attrs = {
            'type': edge.get('type', '')
        }
        
        # Add quote if available
        if 'quote' in edge:
            edge_attrs['quote'] = edge['quote']
        
        G.add_edge(
            edge['source'],
            edge['target'],
            **edge_attrs
        )
    
    return G

def visualize_interactive(G):
    """Create interactive visualization with pyvis and display in notebook"""
    # Use cdn_resources='in_line' to avoid display issues in notebooks
    net = Network(height="1200px", width="100%", directed=True, notebook=True, cdn_resources='in_line')
    
    # Define colors for different node types
    color_map = {
        'person': '#add8e6',  # skyblue
        'organization': '#90ee90',  # lightgreen
        'location': '#fa8072',  # salmon
        'event': '#ffff00',  # yellow
        'product': '#a020f0',  # purple
        'group': '#ffa500',   # orange
        'country': '#ff7f50'  # coral
    }
    
    # Add nodes
    for node_id in G.nodes:
        node_data = G.nodes[node_id]
        
        # Create formatted hover info
        hover_info = f"<div style='max-width:300px;'>"
        hover_info += f"<b>{node_data['name']}</b><br>"
        hover_info += f"<b>Type:</b> {node_data['type']}<br>"
        
        # Add quote if available
        if 'quote' in node_data:
            hover_info += f"<br><b>Quote:</b><br><i>{node_data['quote']}</i><br>"
            
        # Add attributes if available
        if 'attributes' in node_data and node_data['attributes']:
            hover_info += "<br><b>Attributes:</b><br>"
            for key, value in node_data['attributes'].items():
                hover_info += f"- {key}: {value}<br>"
                    
        hover_info += "</div>"
        
        # Add node with custom styling
        net.add_node(
            node_id, 
            label=node_data['name'],
            title=hover_info,
            color=color_map.get(node_data['type'], '#d3d3d3'),
            size=25,
            font={'size': 16, 'face': 'arial'},
            borderWidth=2,
            borderWidthSelected=4,
            shape='dot'
        )
    
    # Add edges with quotes
    for source, target, edge_attrs in G.edges(data=True):
        # Format the tooltip to show the quote
        tooltip = f"<div style='max-width:300px;'>"
        tooltip += f"<b>Relation:</b> {edge_attrs.get('type', '')}"
        
        # Add the quote if available in the edge data
        if 'quote' in edge_attrs:
            tooltip += f"<br><b>Quote:</b><br><i>{edge_attrs['quote']}</i>"
        tooltip += "</div>"
        
        net.add_edge(
            source, 
            target, 
            title=tooltip,
            label=edge_attrs.get('type', ''),
            font={'size': 12, 'align': 'middle'},
            arrows={'to': {'enabled': True, 'type': 'arrow'}},
            color={'color': '#848484', 'highlight': '#FF0000'},
            width=2,
            selectionWidth=3
        )
    
    # Configure physics for more equidistant nodes
    net.repulsion(
        node_distance=200,
        central_gravity=0.2,
        spring_length=200,
        spring_strength=0.05,
        damping=0.09
    )
    
    # Set other layout options
    net.set_options("""
    {
      "interaction": {
        "hover": true,
        "dragNodes": true,
        "dragView": true,
        "navigationButtons": true,
        "multiselect": true,
        "selectable": true,
        "zoomView": true
      },
      "physics": {
        "enabled": true,
        "stabilization": {
          "enabled": true,
          "iterations": 1000,
          "updateInterval": 100,
          "fit": true
        },
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.1,
          "springLength": 250,
          "springConstant": 0.04,
          "damping": 0.09,
          "avoidOverlap": 0.5
        },
        "solver": "barnesHut"
      },
      "layout": {
        "randomSeed": 42,
        "improvedLayout": true
      },
      "edges": {
        "smooth": {
          "enabled": true,
          "type": "dynamic"
        }
      },
      "nodes": {
        "font": {
          "size": 16
        }
      }
    }
    """)
    
    return net

def visualize_matplotlib(G, figsize=(12, 10)):
    """Create static visualization with matplotlib"""
    plt.figure(figsize=figsize)
    
    # Define colors for different node types
    color_map = {
        'person': 'skyblue',
        'organization': 'lightgreen',
        'location': 'salmon',
        'event': 'yellow',
        'product': 'purple',
        'group': 'orange'
    }
    
    # Set node colors based on type
    node_colors = [color_map.get(G.nodes[node]['type'], 'gray') for node in G.nodes]
    
    # Use circular layout for more equidistant nodes
    pos = nx.circular_layout(G)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700, alpha=0.8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, width=1.5, alpha=0.7, arrows=True, arrowsize=15)
    
    # Draw node labels
    labels = {node: G.nodes[node]['name'] for node in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=10, font_family='sans-serif')
    
    # Draw edge labels
    edge_labels = {(u, v): G[u][v]['type'] for u, v in G.edges}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
    
    # Create legend for node types
    legend_handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, 
                     markersize=10, label=node_type) 
                     for node_type, color in color_map.items() if any(G.nodes[n]['type'] == node_type for n in G.nodes)]
    
    plt.legend(handles=legend_handles, loc='upper right')
    plt.axis('off')
    plt.tight_layout()
    plt.show()

def get_llm_output(system_prompt, raw_article, model_name="deepseek-r1-distill-llama-70b"):
    """
    Get output from Groq LLM based on system prompt and article input.
    
    Args:
        system_prompt (str): The system prompt to guide the LLM
        raw_article (str): The article text to analyze
        model_name (str): The model name to use
    
    Returns:
        str: The LLM output content
    """
    client = Groq(api_key="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")
    
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_article}
        ],
        model=model_name,
    )
    
    llm_output = chat_completion.choices[0].message.content
    print("LLM Output:")
    print(llm_output)
    return llm_output

def process_llm_output(llm_output):
    """
    Process LLM output to extract JSON, create graph, and visualize
    """
    try:
        json_result = extract_json_from_llm_output(llm_output)
        data = parse_entity_data(json_result)
        G = create_graph(data) 
        
        print("Static Visualization:")
        visualize_matplotlib(G)

        print("Interactive Visualization:")
        network = visualize_interactive(G)
        network.show("entity_graph.html")
        display(IFrame("entity_graph.html", width="100%", height="800px"))
        
        return G, network
    except ValueError as e:
        print(f"Error: {e}")
        return None, None

# Main execution
if __name__ == "__main__":
    system_prompt = """

You are an expert analyst tasked with extracting a knowledge graph from a news article. Follow these steps:  

1. **Read & Analyze**:  
   - Identify entities (people, organizations, locations, etc.) and their explicit relationships.  
   - Highlight the **exact quotes** from the text that justify each entity and relationship.  

2. **Schema Rules**:  
   - **Nodes**:  
     - `id`: Unique identifier (e.g., `Person_1`).  
     - `name`: Entity name (case-sensitive).  
     - `type`: `person`, `organization`, `location`, `event`, etc.  
     - `quote`: *Exact text snippet* from the article mentioning the entity.  
     - `attributes` (optional): Role, location, aliases.  

   - **Edges**:  
     - `source`: Source node ID.  
     - `target`: Target node ID or event.  
     - `type`: Relationship type (e.g., `ACCUSED_BY`, `OCCURRED_AT`).  
     - `quote`: *Exact text snippet* describing the relationship.  

3. **Constraints**:  
   - **No hallucinations**: Only include entities/relationships explicitly stated in the text.  
   - **Multilingual support**: Preserve quotes in their original language.  
   - **Minimal quotes**: Use the shortest relevant text snippet (e.g., a clause or sentence).  

4. **Output Format (JSON)**:  
```json  
{  
  "nodes": [  
    {  
      "id": "Person_1",  
      "name": "Elon Musk",  
      "type": "person",  
      "quote": "\"Elon Musk (CEO of SpaceX) criticized Jeff Bezos...\"",  
      "attributes": { "role": "CEO of SpaceX" }  
    }  
  ],  
  "edges": [  
    {  
      "source": "Person_1",  
      "target": "Organization_1",  
      "type": "MEMBER_OF",  
      "quote": "\"Elon Musk, CEO of SpaceX, stated...\""  
    }  
  ]  
}  

Example

Input Article:
"During a Senate hearing in Washington D.C., Mark Zuckerberg (CEO of Meta) apologized for data privacy failures. 'We failed to protect user data,' he said. Senator Maria Cruz replied, 'This is unacceptable.'"

Output:
json

{  
  "nodes": [  
    {  
      "id": "Person_1",  
      "name": "Mark Zuckerberg",  
      "type": "person",  
      "quote": "\"Mark Zuckerberg (CEO of Meta) apologized for data privacy failures.\"",  
      "attributes": { "role": "CEO of Meta" }  
    },  
    {  
      "id": "Organization_1",  
      "name": "Meta",  
      "type": "organization",  
      "quote": "\"Mark Zuckerberg (CEO of Meta)...\""  
    },  
    {  
      "id": "Person_2",  
      "name": "Maria Cruz",  
      "type": "person",  
      "quote": "\"Senator Maria Cruz replied, 'This is unacceptable.'\"",  
      "attributes": { "role": "Senator" }  
    },  
    {  
      "id": "Location_1",  
      "name": "Washington D.C.",  
      "type": "location",  
      "quote": "\"During a Senate hearing in Washington D.C....\""  
    }  
  ],  
  "edges": [  
    {  
      "source": "Person_1",  
      "target": "Organization_1",  
      "type": "MEMBER_OF",  
      "quote": "\"Mark Zuckerberg (CEO of Meta)...\""  
    },  
    {  
      "source": "Person_1",  
      "target": "Location_1",  
      "type": "APPEARED_AT",  
      "quote": "\"During a Senate hearing in Washington D.C....\""  
    },  
    {  
      "source": "Person_2",  
      "target": "Person_1",  
      "type": "CRITICIZED",  
      "quote": "\"Senator Maria Cruz replied, 'This is unacceptable.'\""  
    }  
  ]  
}  


"""
    
    raw_article = """
    Chief Adviser Professor Muhammad Yunus returned home Saturday morning, wrapping up his four-day official tour to London.

    A flight of Biman Bangladesh Airlines carrying the Chief Adviser and entourage landed at Hazrat Shahjalal International Airport, Dhaka at about 9:45 am on Saturday, Chief Adviser’s Senior Assistant Press Secretary Foyez Ahammad told BSS.

    While briefing reporters on Thursday, Chief Adviser's Press Secretary Shafiqul Alam said the main focus of Chief Adviser’s tour to London was on recovery of stolen assets.

    During the Sheikh Hasina's reign, US$ 234 billion was siphoned off from Bangladesh to various countries. A part of it was laundered to the UK. So, the major focus of the Prof Yunus’s UK visit was on asset recovery,” he told reporters in London.
    On Friday, BNP acting Chairman Tarique Rahman met Prof Yunus at a city hotel and during the meeting, they discussed Bangladesh’s next general elections, reform and other issues.

    Prof Yunus held a telephone conversation on Friday with former British Prime Minister Gordon Brown focusing on Bangladesh's ongoing economic recovery efforts and the urgent need to enhance educational opportunities for Rohingya children.

    He joined an interactive session with students at his hotel too.

    On 12 June, Prof Yunus received the King Charles III Harmony Award at St James’s Palace in London. The award recognised Prof Yunus's "unique contribution to ensuring harmonious coexistence between people, nature and the environment, bringing about positive changes in the lives of the marginalised communities and building a peaceful, harmonious and sustainable world".

    Catherine West, UK Parliamentary Under-Secretary of State for Indo-Pacific, called on him at his hotel on the same day.

    Besides, the Bangladesh Chief Adviser met Sir Lindsay Hoyle, Speaker of the UK House of Commons, in Westminster, London.

    On 11 June, the UK Secretary of State for Business and Trade and President of the Board of Trade, Jonathan Reynolds, met Prof Yunus at the British Parliament.

    The Chief Adviser spoke at an event at the Royal Institute of International Affairs in Chatham House.

    In addition, UK National Security Adviser Jonathan Powell called on Prof Yunus at his hotel.

    On 10 June, Airbus Executive Vice President Wouter van Wersch and Menzies Aviation Executive Vice President Charles Wyley called on the Bangladesh Chief Adviser expressing their eagerness to build a long-term partnership with Bangladesh.

    Commonwealth Secretary-General Shirley Ayorkor Botchwey met Prof Yunus when she said her organisation was keen to support Bangladesh in political reforms ahead of the planned general election next year.

    A group of UK parliamentarian under the banner of All Party Parliamentary Group also called on the Chief Adviser.

    Prof Yunus reached London on the four-day visit to the United Kingdom on 10 June last.
    """

    # Count tokens
    system_prompt_tokens = count_tokens(system_prompt)
    raw_article_tokens = count_tokens(raw_article)
    total_tokens = system_prompt_tokens + raw_article_tokens

    print(f"System prompt tokens: {system_prompt_tokens}")
    print(f"Raw article tokens: {raw_article_tokens}")
    print(f"Total tokens: {total_tokens}")
    
    # Get LLM output and process
    llm_output = get_llm_output(system_prompt, raw_article)
    G, network = process_llm_output(llm_output)