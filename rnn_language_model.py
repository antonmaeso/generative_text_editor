# Based on https://github.com/dennybritz/rnn-tutorial-rnnlm

import numpy as np
import sys
import json
import operator
from datetime import datetime
import progressbar

vocabulary_size = 8000
unknown_token = "UNK"
sentence_start_token = "start_sentence"
sentence_end_token = "end_sentence"
name = 'corpus'
dict_unigram_freq = {}

with open('corpus/' + name + '.json', 'r') as cp:
    corpus = json.load(cp)

for word in corpus:
    if dict_unigram_freq.has_key(word) and word != '\\':
        dict_unigram_freq[word] += 1
    else:
        dict_unigram_freq[word] = 1

sorted_dict_unigram_freq = sorted(dict_unigram_freq.items(), key=operator.itemgetter(1),reverse=True)
most_freq_words = dict(sorted_dict_unigram_freq[:vocabulary_size])


q_of_UNK = 0
for word in range(len(corpus)-1):
    if corpus[word] not in most_freq_words:
        corpus[word] = unknown_token
        q_of_UNK += 1
most_freq_words[unknown_token] = q_of_UNK

list_of_s = []
sentence = ['start_sentence']
for word in corpus:
    if word != '.' and word != '!' and word != '?' and not word.isdigit():
        sentence.append(word)
    elif word == '.':
        sentence.append('.')
        sentence.append('end_sentence')
        list_of_s.append(sentence)
        sentence = ['start_sentence']
    elif word == '!':
        sentence.append('!')
        sentence.append('end_sentence')
        list_of_s.append(sentence)
        sentence = ['start_sentence']
    elif word == '?':
        sentence.append('?')
        sentence.append('end_sentence')
        list_of_s.append(sentence)
        sentence = ['start_sentence']
    elif word.isdigit():
        sentence.append(word)

most_freq_words['start_sentence'] = len(list_of_s)
most_freq_words['end_sentence'] = len(list_of_s)


id_to_word = {id: word for (id, word) in enumerate(most_freq_words.keys())}
word_to_id = {word: id for (id, word) in enumerate(most_freq_words.keys())}

X_train = np.asarray([[word_to_id[w] for w in sent[:-1]] for sent in list_of_s])
y_train = np.asarray([[word_to_id[w] for w in sent[1:]] for sent in list_of_s])



################################################################
class RNNNumpy:
    def __init__(self, word_dim, corpus_name, hidden_dim=100, bptt_truncate=4):
        # Assign instance variables
        self.word_dim = word_dim
        self.hidden_dim = hidden_dim
        self.bptt_truncate = bptt_truncate
        self.corpus_name = corpus_name
        # Randomly initialize the network parameters
        self.U = np.random.uniform(-np.sqrt(1. / word_dim), np.sqrt(1. / word_dim), (hidden_dim, word_dim))
        self.V = np.random.uniform(-np.sqrt(1. / hidden_dim), np.sqrt(1. / hidden_dim), (word_dim, hidden_dim))
        self.W = np.random.uniform(-np.sqrt(1. / hidden_dim), np.sqrt(1. / hidden_dim), (hidden_dim, hidden_dim))


    def softmax(self, x):
        """Compute softmax values for each sets of scores in x."""
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def forward_propagation(self, x):
        # The total number of time steps
        total_time_steps = len(x)
        # During forward propagation we save all hidden states in s because need them later.
        # We add one additional element for the initial hidden, which we set to 0
        s = np.zeros((total_time_steps + 1, self.hidden_dim))
        s[-1] = np.zeros(self.hidden_dim)
        # The outputs at each time step. Again, we save them for later.
        o = np.zeros((total_time_steps, self.word_dim))
        # For each time step...
        for t in np.arange(total_time_steps):
            # Note that we are indexing U by x[t]. This is the same as multiplying U with a one-hot vector.
            s[t] = np.tanh(self.U[:, x[t]] + self.W.dot(s[t - 1]))
            o[t] = self.softmax(self.V.dot(s[t]))
        return [o, s]

    def predict(self, x):
        # Perform forward propagation and return index of the highest score
        o, s = self.forward_propagation(x)
        print o
        return np.argmax(o, axis=1)

    def calculate_total_loss(self, x, y):
        L = 0
        # For each sentence...
        for i in np.arange(len(y)):
            o, s = self.forward_propagation(x[i])
            # We only care about our prediction of the "correct" words
            correct_word_predictions = o[np.arange(len(y[i])), y[i]]
            # Add to the loss based on how off we were
            L += -1 * np.sum(np.log(correct_word_predictions))
        return L

    def calculate_loss(self, x, y):
        # Divide the total loss by the number of training examples
        N = np.sum((len(y_i) for y_i in y))
        return self.calculate_total_loss(x, y) / N

    def bptt(self, x, y):
        T = len(y)
        # Perform forward propagation
        o, s = self.forward_propagation(x)
        # We accumulate the gradients in these variables
        dLdU = np.zeros(self.U.shape)
        dLdV = np.zeros(self.V.shape)
        dLdW = np.zeros(self.W.shape)
        delta_o = o
        delta_o[np.arange(len(y)), y] -= 1.
        # For each output backwards...
        for t in np.arange(T)[::-1]:
            dLdV += np.outer(delta_o[t], s[t].T)
            # Initial delta calculation
            delta_t = self.V.T.dot(delta_o[t]) * (1 - (s[t] ** 2))
            # Backpropagation through time (for at most self.bptt_truncate steps)
            for bptt_step in np.arange(max(0, t - self.bptt_truncate), t + 1)[::-1]:
                # print "Backpropagation step t=%d bptt step=%d " % (t, bptt_step)
                dLdW += np.outer(delta_t, s[bptt_step - 1])
                dLdU[:, x[bptt_step]] += delta_t
                # Update delta for next step
                delta_t = self.W.T.dot(delta_t) * (1 - s[bptt_step - 1] ** 2)
        return [dLdU, dLdV, dLdW]

    def gradient_check(self, x, y, h=0.001, error_threshold=0.01):
        # Calculate the gradients using backpropagation. We want to checker if these are correct.
        bptt_gradients = model.bptt(x, y)
        # List of all parameters we want to check.
        model_parameters = ['U', 'V', 'W']
        # Gradient check for each parameter
        for pidx, pname in enumerate(model_parameters):
            # Get the actual parameter value from the mode, e.g. model.W
            parameter = operator.attrgetter(pname)(self)
            print "Performing gradient check for parameter %s with size %d." % (pname, np.prod(parameter.shape))
            # Iterate over each element of the parameter matrix, e.g. (0,0), (0,1), ...
            it = np.nditer(parameter, flags=['multi_index'], op_flags=['readwrite'])
            while not it.finished:
                ix = it.multi_index
                # Save the original value so we can reset it later
                original_value = parameter[ix]
                # Estimate the gradient using (f(x+h) - f(x-h))/(2*h)
                parameter[ix] = original_value + h
                gradplus = model.calculate_total_loss([x], [y])
                parameter[ix] = original_value - h
                gradminus = model.calculate_total_loss([x], [y])
                estimated_gradient = (gradplus - gradminus) / (2 * h)
                # Reset parameter to original value
                parameter[ix] = original_value
                # The gradient for this parameter calculated using backpropagation
                backprop_gradient = bptt_gradients[pidx][ix]
                # calculate The relative error: (|x - y|/(|x| + |y|))
                relative_error = np.abs(backprop_gradient - estimated_gradient) / (
                np.abs(backprop_gradient) + np.abs(estimated_gradient))
                # If the error is to large fail the gradient check
                if relative_error > error_threshold:
                    print "Gradient Check ERROR: parameter=%s ix=%s" % (pname, ix)
                    print "+h Loss: %f" % gradplus
                    print "-h Loss: %f" % gradminus
                    print "Estimated_gradient: %f" % estimated_gradient
                    print "Backpropagation gradient: %f" % backprop_gradient
                    print "Relative Error: %f" % relative_error
                    return
                it.iternext()
            print "Gradient check for parameter %s passed." % (pname)

    def sgd_step(self, x, y, learning_rate):
        # Calculate the gradients
        dLdU, dLdV, dLdW = self.bptt(x, y)
        # Change parameters according to gradients and learning rate
        self.U -= learning_rate * dLdU
        self.V -= learning_rate * dLdV
        self.W -= learning_rate * dLdW

    def load_model_parameters(self, path, model):
        print 'started loading model'
        npzfile = np.load(path)
        U, V, W = npzfile["U"], npzfile["V"], npzfile["W"]
        model.hidden_dim = U.shape[0]
        model.word_dim = U.shape[1]
        model.U = U
        model.V = V
        model.W = W
        print "Loaded model parameters from %s. hidden_dim=%d word_dim=%d" % (path, U.shape[0], U.shape[1])


        with open('./corpus/' + self.corpus_name + '.json', 'r') as rnn:
            model_parameters = json.load(rnn)
            last_model = model_parameters[-1]
            model.word_dim = last_model["word_dim"]
            model.hidden_dim = last_model["hidden_dim"]
            model.bptt_truncate = last_model["bptt_truncate"]
            current_epoch = last_model["current_epoch"]
            current_loss = last_model["current_loss"]
            learning_rate = last_model["current_learning_rate"]
            num_examples_seen = last_model["num_examples_seen"]
            model.corpus_name = self.corpus_name
            print 'ended loading model'
            return (current_epoch, current_loss, learning_rate, num_examples_seen)


    # Outer SGD Loop
    # - model: The RNN model instance
    # - X_train: The training data set
    # - y_train: The training data labels
    # - learning_rate: Initial learning rate for SGD
    # - nepoch: Number of times to iterate through the complete dataset
    # - evaluate_loss_after: Evaluate the loss after this many epochs
    def train_with_sgd(model, X_train, y_train, learning_rate=0.005, nepoch=100, evaluate_loss_after=5, saving_model_after=5, load_existing_model=''):
        # We keep track of the losses so we can plot them later
        # load model and continue training

        if load_existing_model:
            parrameters = model.load_model_parameters(load_existing_model, model)
            learning_rate = parrameters[2]
            losses = parrameters[1][:-1]
            num_examples_seen = parrameters[1][-1][0]
            for epoch in range(parrameters[0]+1,nepoch):
                progress_bar = ''
                # Optionally evaluate the loss
                if (epoch % evaluate_loss_after == 0):
                    loss = model.calculate_loss(X_train, y_train)
                    losses.append((num_examples_seen, loss))
                    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print "%s: Loss after num_examples_seen=%d epoch=%d: %f" % (time, num_examples_seen, epoch, loss)
                    # Adjust the learning rate if loss increases
                    if (len(losses) > 1 and losses[-1][1] > losses[-2][1]):
                        learning_rate = learning_rate * 0.5
                        print "Setting learning rate to %f" % learning_rate
                    sys.stdout.flush()
                if epoch % saving_model_after == 0:
                    model.save_model_parameters('./corpus/training_model_' + model.corpus_name, model=model,
                                                current_epoch=epoch, total_number_of_epoch=nepoch,
                                                learning_rate=learning_rate, evaluation_loss_rate=evaluate_loss_after,
                                                saving_rate=saving_model_after,
                                                current_loss=losses, num_examples_seen=num_examples_seen)
                # For each training example...
                with progressbar.ProgressBar(max_value=len(y_train)) as bar:
                    for i in range(len(y_train)):
                        # One SGD step

                        model.sgd_step(X_train[i], y_train[i], learning_rate)
                        num_examples_seen += 1
                        bar.update(i)

                print 'completed epochs: ' + str(epoch) + '/' + str(nepoch)
        else:
            losses = []
            num_examples_seen = 0
            for epoch in range(nepoch):
                # Optionally evaluate the loss
                if (epoch % evaluate_loss_after == 0):
                    loss = model.calculate_loss(X_train, y_train)
                    losses.append((num_examples_seen, loss))
                    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print "%s: Loss after num_examples_seen=%d epoch=%d: %f" % (time, num_examples_seen, epoch, loss)
                    # Adjust the learning rate if loss increases
                    if (len(losses) > 1 and losses[-1][1] > losses[-2][1]):
                        learning_rate = learning_rate * 0.5
                        print "Setting learning rate to %f" % learning_rate
                    sys.stdout.flush()
                if epoch % saving_model_after == 0:
                    model.save_model_parameters('./corpus/training_model_' + model.corpus_name, model=model,
                                                current_epoch=epoch, total_number_of_epoch=nepoch,
                                                learning_rate=learning_rate, evaluation_loss_rate=evaluate_loss_after, saving_rate=saving_model_after,
                                                current_loss=losses, num_examples_seen=num_examples_seen)
                # For each training example...
                with progressbar.ProgressBar(max_value=len(y_train)) as bar:
                    for i in range(len(y_train)):
                        # One SGD step

                        model.sgd_step(X_train[i], y_train[i], learning_rate)
                        num_examples_seen += 1
                        bar.update(i)

                print 'completed epochs: ' + str(epoch) + '/' + str(nepoch)


    def save_model_parameters(self, outfile, model, current_epoch, total_number_of_epoch, learning_rate, evaluation_loss_rate, saving_rate, current_loss, num_examples_seen):
        print "Start saving training progress of %s.json" % self.corpus_name
        U, V, W = model.U, model.V, model.W
        np.savez(outfile, U=U, V=V, W=W)
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        model_parameters = [
            {'time': time, 'current_epoch': current_epoch, 'total_number_of_epochs': total_number_of_epoch,
             'current_learning_rate': learning_rate, 'evaluation_loss_rate': evaluation_loss_rate,'saving_rate': saving_rate,
             'current_loss': current_loss, 'word_dim': self.word_dim, 'hidden_dim': self.hidden_dim,
             'bptt_truncate': self.bptt_truncate, 'num_examples_seen': num_examples_seen}]

        if current_epoch != 0:
            with open('corpus/' + self.corpus_name + '.json', 'r') as outfile:
                data = json.load(outfile)
                data.extend(model_parameters)
            outfile.close()
            with open('corpus/' + self.corpus_name + '.json', 'w') as outfile:
                json.dump(data, outfile)
            outfile.close()
        else:
            with open('corpus/' + self.corpus_name + '.json', 'w') as outfile:
                json.dump(model_parameters, outfile)
            outfile.close()
        print "End saving training progress of %s.json" % self.corpus_name



e_m='/Users/antonscomputer/Documents/Documents/generative_text_editor/corpus/training_model_rnn_test.npz'

np.random.seed(10)
# Train on a small subset of the data to see what happens
model = RNNNumpy(vocabulary_size+3,corpus_name='rnn_full_vocab')

losses = model.train_with_sgd(X_train, y_train, nepoch=20, evaluate_loss_after=1,saving_model_after=1)

def generate_sentence(model):
    # We start the sentence with the start token
    new_sentence = [word_to_id[sentence_start_token]]
    # Repeat until we get an end token
    while not new_sentence[-1] == word_to_id[sentence_end_token]:
        next_word_probs = model.forward_propagation(new_sentence)[0]
        # We don't want to sample unknown words
        samples = np.random.multinomial(1, next_word_probs[-1])
        sampled_word = np.argmax(samples)
        new_sentence.append(sampled_word)
    sentence_str = [id_to_word[x] for x in new_sentence[1:-1]]
    return sentence_str

def predict_next_word(model, sentance_so_far):
    # We start the sentence with the start token
    sentance_so_far = [word_to_id[x] for x in sentance_so_far]

    next_word_probs = model.forward_propagation(sentance_so_far)[0]

    samples = np.random.multinomial(1, next_word_probs[-1])
    sampled_word = samples.argsort()[-20:][::-1]

    next_word_probs = [id_to_word[x] for x in sampled_word]
    return next_word_probs