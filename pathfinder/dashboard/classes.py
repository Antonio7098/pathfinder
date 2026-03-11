class node():
    language_converter = {
        'js' : 'javascript',
        'py' : 'python'
    }
    def __init__(
        self,
        node_id,
        entry_point=False,
        end_point=False,
        normalised_risk_score=0.0,
        confidence=0.0,
        exploitability=0.0,
        privelidge_gain=0.0,
        data_access_value=0.0,
        lateral_movement_value=0.0,
        detection_risk=0.0,
    ):
        self.node_type = 'file'
        self.node_id = node_id
        extension = self.node_id.rsplit('.', 1)[-1] if '.' in self.node_id else ''
        self.language = self.language_converter.get(extension, extension or 'unknown')
        self.entry_point = entry_point
        self.end_point = end_point
        self.normalised_risk_score = normalised_risk_score
        self.confidence = confidence
        self.exploitability = exploitability
        self.privelidge_gain = privelidge_gain
        self.data_access_value = data_access_value
        self.lateral_movement_value = lateral_movement_value
        self.detection_risk = detection_risk

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
    def __init__(
        self,
        source_node,
        target_node,
        vulnerability="default",
        transition_likelihood=0.0,
        detection_risk=0.0,
        edge_attack_cost=0.0,
    ):
        self.id = source_node + '>' + target_node
        self.type = 'attack'

        self.source_node = source_node
        self.target_node = target_node

        self.vulnerability = vulnerability
        self.transition_likelihood = transition_likelihood
        self.detection_risk = detection_risk
        self.edge_attack_cost = edge_attack_cost
    
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

    def __init__(
        self,
        node_id,
        name,
        kind,
        layer,
        summary,
        files,
        file_count,
        files_by_language,
        rationale,
        entry_point=False,
        end_point=False,
        normalised_risk_score=0.0,
        confidence=0.0,
        exploitability=0.0,
        privelidge_gain=0.0,
        data_access_value=0.0,
        lateral_movement_value=0.0,
        detection_risk=0.0,
    ):
        self.node_type = 'service'
        self.node_id = node_id
        self.name = name
        dominant_language = sorted(files_by_language.items(), key=lambda item: (-item[1], item[0]))[0][0] if files_by_language else 'unknown'
        self.language = self.language_converter.get(dominant_language, dominant_language)
        self.kind = kind
        self.layer = layer
        self.summary = summary
        self.files = files
        self.file_count = file_count
        self.files_by_language = files_by_language
        self.rationale = rationale
        self.entry_point = entry_point
        self.end_point = end_point
        self.normalised_risk_score = normalised_risk_score
        self.confidence = confidence
        self.exploitability = exploitability
        self.privelidge_gain = privelidge_gain
        self.data_access_value = data_access_value
        self.lateral_movement_value = lateral_movement_value
        self.detection_risk = detection_risk

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
