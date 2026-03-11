import json
import os
import random

import nltk
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("wordnet", quiet=True)


class ChatbotModel(nn.Module):
    def __init__(self, input_size, output_size):
        super().__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.fc2 = nn.Linear(128, 64)
        self.fc3 = nn.Linear(64, output_size)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        x = self.dropout(x)
        return self.fc3(x)


class ChatbotAssistant:
    def __init__(self, intents_path):
        self.model = None
        self.intents_path = intents_path

        self.documents = []
        self.vocabulary = []
        self.intents = []
        self.intents_responses = {}

        self.X = None
        self.Y = None

    @staticmethod
    def tokenize_and_lemmatize(text):
        lemmatizer = nltk.WordNetLemmatizer()
        words = nltk.word_tokenize(text)
        return [lemmatizer.lemmatize(word.lower()) for word in words]

    def bag_of_words(self, words):
        words_set = set(words)
        return [1 if word in words_set else 0 for word in self.vocabulary]

    def parse_intents(self):
        if not os.path.exists(self.intents_path):
            raise FileNotFoundError(f"Intents file not found: {self.intents_path}")

        with open(self.intents_path, "r", encoding="utf-8") as f:
            intents_data = json.load(f)

        for intent in intents_data.get("intents", []):
            tag = intent.get("tag") or intent.get("tags")
            responses = intent.get("responses") or intent.get("response") or []
            patterns = intent.get("patterns", [])

            if not tag or not patterns:
                continue

            if tag not in self.intents:
                self.intents.append(tag)

            if isinstance(responses, str):
                responses = [responses]
            self.intents_responses[tag] = responses

            for pattern in patterns:
                tokens = self.tokenize_and_lemmatize(pattern)
                self.vocabulary.extend(tokens)
                self.documents.append((tokens, tag))

        self.vocabulary = sorted(set(self.vocabulary))

        if not self.documents:
            raise ValueError("No valid intents/patterns found.")

    def prepare_data(self):
        bags = []
        labels = []

        for tokens, tag in self.documents:
            bags.append(self.bag_of_words(tokens))
            labels.append(self.intents.index(tag))

        self.X = np.array(bags, dtype=np.float32)
        self.Y = np.array(labels, dtype=np.int64)

    def train_model(self, batch_size=8, lr=0.001, epochs=200):
        if self.X is None or self.Y is None:
            raise RuntimeError("Call parse_intents() and prepare_data() first.")
        if len(self.X) == 0 or len(self.Y) == 0:
            raise ValueError("Training data is empty. Check intents/patterns in Spoken.json.")
        if self.X.ndim != 2:
            raise ValueError(f"self.X must be 2D, got shape {self.X.shape}")
        if self.Y.ndim != 1:
            raise ValueError(f"self.Y must be 1D, got shape {self.Y.shape}")

        X_tensor = torch.tensor(self.X, dtype=torch.float32)
        y_tensor = torch.tensor(self.Y, dtype=torch.long)

        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        self.model = ChatbotModel(self.X.shape[1], len(self.intents))
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=lr)

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0.0
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                logits = self.model(batch_x)
                loss = criterion(logits, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            if (epoch + 1) % 50 == 0:
                avg_loss = total_loss / max(1, len(loader))
                print(f"Epoch {epoch + 1}/{epochs} - loss: {avg_loss:.4f}")

    def predict_intent(self, text):
        if self.model is None:
            raise RuntimeError("Model is not trained yet.")

        tokens = self.tokenize_and_lemmatize(text)
        bow = torch.tensor([self.bag_of_words(tokens)], dtype=torch.float32)

        self.model.eval()
        with torch.no_grad():
            logits = self.model(bow)
            probs = torch.softmax(logits, dim=1)
            confidence, index = torch.max(probs, dim=1)

        return self.intents[index.item()], confidence.item()

    def load_model(self, model_path, dimension_path):
        with open(dimension_path, 'r') as f:
            dimensions = json.load(f)

        self.model = ChatbotModel(dimensions['input_size'], dimensions['output_size'])
        self.model.load_state_dict(torch.load(model_path, weight_only = True))

    def process_message(self, input_message):
        words = self.tokenize_and_lemmatize(input_message)
        bag = self.bag_of_words(words)

        bag_tensor = torch.tensor([bag], dtype=torch.float32)

        self.model.eval()
        with torch.no_grad():
            predictions = self.model(bag_tensor)

        predicted_class_index = torch.argmax(predictions, dim=1).item()
        predicted_intent = self.intents[predicted_class_index]

        if self.intents_responses[predicted_intent]:
            return random.choice(self.intents_responses[predicted_intent])
        else:
            return None

    def test_get_stocks_from_defined_list(self):
        stocks = ['App', 'META', 'AMZN', 'GOOGL', 'TSLA']
        result = self.bot.get_stocks()
        for stock in result:
            self.assertIn(stock, stocks)

    def respond(self, text, threshold=0.4):
        intent, confidence = self.predict_intent(text)
        if confidence < threshold:
            return "Sorry, I don't Understand. Try another sentence."

        responses = self.intents_responses.get(intent, [])
        if not responses:
            return "I understand the meaning, but there is no answer for that sentence yet."

        return random.choice(responses)



if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    intents_file = os.path.join(base_dir, "Spoken.json")

    bot = ChatbotAssistant(intents_file)
    bot.parse_intents()
    bot.prepare_data()
    bot.train_model(batch_size=8, lr=0.001, epochs=200)

    print("Chatbot ready. button 'quit' to Exits.")
    while True:
        user_text = input("You: ").strip()
        if user_text.lower() in {"quit", "exit"}:
            print("Bot: Good Bye!")
            break
        print("Bot:", bot.respond(user_text))
