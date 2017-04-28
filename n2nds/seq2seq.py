import tensorflow as tf


class Model:
    def __init__(self, config, data, is_train=True):
        embedding = tf.get_variable("embedding", [config.VOCAB_SIZE, config.EMBED_SIZE], dtype=tf.float32)
        utter_indices = tf.Variable(data.indices, name="utter_indices")
        utter_lengths = tf.Variable(data.lengths, name="utter_lengths")
        utter_weights = tf.Variable(data.weights, name="utter_weights")
        utter_embs = tf.nn.embedding_lookup(embedding, utter_indices)
        encoder = tf.contrib.rnn.BasicLSTMCell(config.UNIT_SIZE, state_is_tuple=True,
                                               reuse=tf.get_variable_scope().reuse)
        decoder = tf.contrib.rnn.BasicLSTMCell(config.UNIT_SIZE, state_is_tuple=True,
                                               reuse=tf.get_variable_scope().reuse)

        self.initial_enc_state = encoder.zero_state(config.BATCH_SIZE, tf.float32)
        enc_state = self.initial_enc_state
        with tf.variable_scope("encoder"):
            enc_outputs, _ = tf.nn.dynamic_rnn(encoder, utter_embs[:, 0, :, :], utter_lengths[:, 0],
                                               initial_state=enc_state)
            utter_lens = utter_lengths[:, 0]
            mask = tf.logical_and(tf.sequence_mask(utter_lens, config.SEQ_SIZE),
                                  tf.logical_not(tf.sequence_mask(utter_lens - 1, config.SEQ_SIZE)))
            enc_output = tf.boolean_mask(enc_outputs, mask)
            # for time_step in range(config.SEQ_SIZE):
            #     if time_step > 0:
            #         tf.get_variable_scope().reuse_variables()
            #     enc_output, enc_state = encoder(utter_embs[:, 0, time_step, :], enc_state)

        self.initial_dec_state = decoder.zero_state(config.BATCH_SIZE, tf.float32)
        dec_state = self.initial_dec_state
        dec_outputs = []
        softmax_w = tf.get_variable("softmax_w", [config.EMBED_SIZE, config.VOCAB_SIZE], dtype=tf.float32)
        softmax_b = tf.get_variable("softmax_b", [config.VOCAB_SIZE], dtype=tf.float32)

        self.fuck_inputs = []
        self.fuck_outputs = []
        self.fuck_previous_embeddings = []

        with tf.variable_scope("decoder"):
            for time_step in range(config.SEQ_SIZE):
                if time_step == 0:
                    dec_output, dec_state = decoder(enc_output, dec_state)
                    self.fuck_previous_embeddings.append(enc_output)
                else:
                    tf.get_variable_scope().reuse_variables()
                    if is_train:
                        dec_output, dec_state = decoder(utter_embs[:, 1, time_step - 1, :], dec_state)
                    else:
                        dec_output_index = tf.argmax(tf.matmul(dec_output, softmax_w) + softmax_b, axis=1)
                        self.fuck_inputs.append(dec_output_index)
                        previous_embedding = tf.nn.embedding_lookup(embedding, dec_output_index)
                        dec_output, dec_state = decoder(previous_embedding, dec_state)
                        self.fuck_previous_embeddings.append(previous_embedding)
                dec_outputs.append(dec_output)  # outputs: SEQ_SIZE * BATCH * EMB_SIZE
                self.fuck_outputs.append(dec_output)

        outputs = tf.reshape(tf.concat(dec_outputs, axis=1), [-1, config.EMBED_SIZE])
        # self.fuck_inputs=tf.reshape(self.fuck_inputs,[-1])

        logits = tf.matmul(outputs, softmax_w) + softmax_b
        self.pred = tf.argmax(logits, 1)
        self.fuck_logits = logits
        targets = tf.reshape(utter_indices[:, 1], [-1])
        # targets = tf.reshape(utter_indices[:, 1],[config.BATCH_SIZE, config.SEQ_SIZE])
        loss = tf.contrib.legacy_seq2seq.sequence_loss_by_example(
            [logits],
            [targets],
            [tf.to_float(tf.reshape(utter_weights, [config.BATCH_SIZE * config.SEQ_SIZE]))])
        self.cost = tf.reduce_sum(loss) / config.BATCH_SIZE
        opt = tf.train.AdamOptimizer()
        self.minimizier = opt.minimize(loss)

        tf.summary.scalar('loss', self.cost)
        self.merged = tf.summary.merge_all()
