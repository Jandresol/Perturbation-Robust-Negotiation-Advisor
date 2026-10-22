const { test } = require('node:test');
const assert = require('node:assert/strict');
const M = require('../model');
const fixture = require('../example-package.json');
const fresh = () => ({ events: [], commitments: [] });
const offer = { type: 'offer', speaker: 'us', actionIds: ['a1', 'b1'], text: 'Exchange both actions.' };
test('package validates source quotes and action references', () => {
  assert.equal(M.validate(fixture), fixture);
  const p = structuredClone(fixture); p.facts[0].quote = 'Invented claim';
  assert.throws(() => M.validate(p), /verbatim/);
  p.facts[0].quote = fixture.facts[0].quote; p.strategies[0].actionIds = ['unknown'];
  assert.throws(() => M.validate(p), /Unknown strategy actions/);
});
test('offers stay nonbinding until another party confirms exact acceptance', () => {
  const s = M.applyEvent(fresh(), offer, fixture);
  assert.deepEqual(s.commitments, []);
  assert.throws(() => M.applyEvent(s, { ...offer, type: 'accept', offerId: 'event-1' }, fixture), /other party/);
  assert.throws(() => M.applyEvent(s, { ...offer, speaker: 'opponent', type: 'accept', offerId: 'event-1', actionIds: ['a1'] }, fixture), /full offer/);
  const accepted = M.applyEvent(s, { ...offer, speaker: 'opponent', type: 'accept', offerId: 'event-1' }, fixture);
  assert.deepEqual(accepted.commitments, ['a1', 'b1']);
  assert.deepEqual(s.commitments, []);
  assert.throws(() => M.applyEvent(accepted, offer, fixture), /already binding/);
});
test('rejected offers cannot later be accepted, and notes preserve commitments', () => {
  const s = M.applyEvent(fresh(), offer, fixture);
  const rejected = M.applyEvent(s, { type: 'reject', speaker: 'opponent', text: 'Declined', actionIds: [], offerId: 'event-1' }, fixture);
  assert.deepEqual(rejected.commitments, []);
  assert.throws(() => M.applyEvent(rejected, { ...offer, type: 'accept', speaker: 'opponent', offerId: 'event-1' }, fixture), /unresolved/);
  assert.deepEqual(M.applyEvent(rejected, { type: 'note', speaker: 'us', text: 'Ask why', actionIds: [] }, fixture).commitments, []);
});
test('empty results are supported without inventing scores', () => {
  const p = { ...fixture, strategies: [], variants: [], pipeline: [] };
  assert.equal(M.validate(p), p);
  const invalid = structuredClone(fixture); invalid.strategies[0].meanScore = 2;
  assert.throws(() => M.validate(invalid), /between 0 and 1/);
});
test('PDF source pages preserve numbered provenance and reject malformed metadata', () => {
  const p = structuredClone(fixture);
  p.sources[0].pages = [{ number: 1, text: p.sources[0].text }];
  assert.equal(M.validate(p), p);
  p.sources[0].pages.push({ number: 1, text: 'duplicate page' });
  assert.throws(() => M.validate(p), /Invalid source pages/);
});
test('questions, tentative agreements, and unmodeled issues never bind or resolve an offer', () => {
  let session = M.applyEvent(fresh(), offer, fixture);
  for (const type of ['question', 'tentative', 'unmodeled']) {
    const event = { type, speaker: 'opponent', text: 'A condition needs discussion', actionIds: [], offerId: 'event-1' };
    session = M.applyEvent(session, event, fixture);
    assert.deepEqual(session.commitments, []);
    assert.throws(() => M.applyEvent(session, { ...event, actionIds: ['a1'] }, fixture), /cannot add/);
  }
  const accepted = M.applyEvent(session, { ...offer, type: 'accept', speaker: 'opponent', offerId: 'event-1' }, fixture);
  assert.deepEqual(accepted.commitments, ['a1', 'b1']);
});

test('source-only rehearsals cannot create modeled offers or binding commitments', () => {
  const session = {...fresh(),mode:'source-rehearsal'};
  assert.throws(()=>M.applyEvent(session,offer,fixture),/Source-only/);
  const recorded=M.applyEvent(session,{type:'tentative',speaker:'us',text:'We might agree after clarifying access.',actionIds:[]},fixture);
  assert.deepEqual(recorded.commitments,[]);
});
