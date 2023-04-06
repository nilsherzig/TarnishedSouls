import db
from Classes.enemy_logic import EnemyLogic
class Enemy:
    def __init__(self, idEnemy):
        result = db.get_enemy_with_id(idEnemy)
        self.id = idEnemy
        self.name = result[0]
        self.logic = EnemyLogic(result[1])
        self.description = result[2]
        self.health = result[3]
        self.runes = result[4]
        self.moves = db.get_enemy_moves_with_enemy_id(idEnemy)

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name

    def get_logic(self):
        return self.logic

    def get_description(self):
        return self.description

    def get_health(self):
        return self.health

    def get_runes(self):
        return self.runes