const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(bodyParser.json());

// MongoDB Connection
mongoose.connect(process.env.MONGO_URI || 'mongodb://localhost:27017/civix')
    .then(() => console.log('MongoDB Connected'))
    .catch(err => console.log('MongoDB Connection Error:', err));

// Survey Model
const SurveySchema = new mongoose.Schema({
    size: String,
    loc: String,
    emp: String,
    cli: String,
    area: String,
    date: String,
    time: String,
    createdAt: { type: Date, default: Date.now }
});

const Survey = mongoose.model('Survey', SurveySchema);

// Routes
app.get('/api/surveys', async (req, res) => {
    try {
        const surveys = await Survey.find().sort({ createdAt: -1 });
        res.json(surveys);
    } catch (err) {
        res.status(500).json({ message: err.message });
    }
});

app.post('/api/surveys', async (req, res) => {
    const survey = new Survey(req.body);
    try {
        const newSurvey = await survey.save();
        res.status(201).json(newSurvey);
    } catch (err) {
        res.status(400).json({ message: err.message });
    }
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
