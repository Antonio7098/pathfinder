from random import randint, choice

class node():
    language_converter = {
        'js' : 'javascript',
        'py' : 'python'
    }
    def __init__(self, node_id, entry_point=False, end_point=False):
        self.node_type = 'file'
        self.node_id = node_id
        self.language = self.language_converter[self.node_id.split('.')[1]]
        self.entry_point = entry_point
        self.end_point = end_point
        self.normalised_risk_score = (randint(0,100))/100
        self.confidence = (randint(0,100))/100
        self.exploitability = (randint(0,100))/100
        self.privelidge_gain = (randint(0,100))/100
        self.data_access_value = (randint(0,100))/100
        self.lateral_movement_value = (randint(0,100))/100
        self.detection_risk = (randint(0,100))/100

    def aggregate_score(self):
        if self.end_point:
            return self.data_access_value * 5 + self.privelidge_gain * 2
        if self.entry_point:
            return self.exploitability * 5 + self.detection_risk * 2
        return 1
    
    def node_value(self):
        if self.end_point:
            return self.data_access_value * 5 + self.privelidge_gain * 2
        if self.entry_point:
            return self.exploitability * 3
        return self.lateral_movement_value




class edge():
    VULNERABILITIES = [
        "sql_injection",
        "command_injection",
        "path_traversal",
        "ssrf",
        "prototype_pollution",
        "insecure_deserialization",
        "hardcoded_secret",
        "auth_bypass",
        "dependency_confusion",
        "xxe"
    ]

    def __init__(self, source_node, target_node):
        self.id = source_node + '>' + target_node
        self.type = 'attack'

        self.source_node = source_node
        self.target_node = target_node

        self.vulnerability = choice(self.VULNERABILITIES)

        self.transition_likelihood = randint(0,100)/100
        self.detection_risk = randint(0,100)/100
        self.edge_attack_cost = randint(0,100)/100
    
    def aggregate(self):
        return (self.transition_likelihood + self.detection_risk + self.edge_attack_cost)/3
    
    def edge_cost(self):
        return (
        self.edge_attack_cost * 2 +
        self.detection_risk * 3 +
        (1 - self.transition_likelihood)
    )
        
        
class service_node():
    language_converter = {
        'js' : 'javascript',
        'py' : 'python'
    }

    def __init__(self, node_id, name, kind, layer, summary, files, file_count, files_by_language, rationale, entry_point=False, end_point=False):
        self.node_type = 'service'
        self.node_id = node_id
        self.name = name
        self.language = self.language_converter[self.node_id.split('.')[1]]
        self.kind = kind
        self.layer = layer
        self.summary = summary
        self.files = files
        self.file_count = file_count
        self.files_by_language = files_by_language
        self.rationale = rationale
        self.entry_point = entry_point
        self.end_point = end_point
        self.normalised_risk_score = (randint(0,100))/100
        self.confidence = (randint(0,100))/100
        self.exploitability = (randint(0,100))/100
        self.privelidge_gain = (randint(0,100))/100
        self.data_access_value = (randint(0,100))/100
        self.lateral_movement_value = (randint(0,100))/100
        self.detection_risk = (randint(0,100))/100

    def aggregate_score(self):
        if self.end_point:
            return self.data_access_value * 5 + self.privelidge_gain * 2
        if self.entry_point:
            return self.exploitability * 5 + self.detection_risk * 2
        return 1
    
    def node_value(self):
        if self.end_point:
            return self.data_access_value * 5 + self.privelidge_gain * 2
        if self.entry_point:
            return self.exploitability * 3
        return self.lateral_movement_value