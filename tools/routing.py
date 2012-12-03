#!/usr/bin/env python
# Copyright (c) 2012 maidsafe.net limited
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#     * Neither the name of the maidsafe.net limited nor the names of its
#     contributors may be used to endorse or promote products derived from this
#     software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys
import datetime
import subprocess
import utils
import random
from subprocess import Popen, PIPE, STDOUT
from time import sleep

num_of_nodes = 20
num_of_bootstraps = 2
num_of_vaults = num_of_nodes / 2 - num_of_bootstraps
num_of_clients = num_of_nodes - num_of_vaults - num_of_bootstraps


def SetupKeys(num):
  print("Setting up keys ... ")
  return subprocess.call(['./routing_key_helper', '-c', '-p', '-n', str(num)], stdout=PIPE)


def SearchKeyWordLine(process, keyword, timeout):
  t_start = datetime.datetime.now()
  next_line = process.stdout.readline()
  while next_line.find(keyword) == -1:
    next_line = process.stdout.readline()
    # print 'process\t' + next_line.rstrip()
    time_delta = datetime.datetime.now() - t_start
    if time_delta >= datetime.timedelta(seconds=timeout):
      return -1
  return next_line


def ExtractNodeEndpoint(p_b):
  peer_line = SearchKeyWordLine(p_b, 'Current BootStrap node endpoint info', 3)
  if peer_line == -1:
    return -1
  peer = peer_line.split()[7]
  return peer


def ParseSecondsFromString(duration):
  times = duration.split(':')
  hour = float(times[0])
  minute = float(times[1])
  second = float(times[2])
  return hour * 3600 + minute * 60 + second


def SetupBootstraps():
  p_b0 = Popen('./routing_node -s -b -i 0', shell = True, stdout=PIPE, stdin=PIPE)
  p_b1 = Popen('./routing_node -s -b -i 1', shell = True, stdout=PIPE, stdin=PIPE)

  peer_0 = ExtractNodeEndpoint(p_b0)
  if peer_0 == -1:
    KillBootstraps(p_b0, p_b1)
    return -1

  peer_1 = ExtractNodeEndpoint(p_b1)
  if peer_1 == -1:
    KillBootstraps(p_b0, p_b1)
    return -1
  sleep(1)

  p_b0.stdin.write('peer ' + peer_1 + '\n')
  p_b1.stdin.write('peer ' + peer_0 + '\n')

  p_b0.stdin.write('zerostatejoin\n')
  p_b1.stdin.write('zerostatejoin\n')
  sleep(1)
  print("Setup boostrap nodes ...")
  return [peer_0, p_b0, p_b1]


def AddRoutingObject(peer, idx):
  if idx < (num_of_nodes / 2):
    p_v = Popen('./routing_node -s -i ' + str(idx) + ' -p ' + peer, shell = True, stdout=PIPE, stdin=PIPE)
  if idx >= (num_of_nodes / 2):
    p_v = Popen('./routing_node -s -c -i ' + str(idx) + ' -p ' + peer, shell = True, stdout=PIPE, stdin=PIPE)

  key_line = SearchKeyWordLine(p_v, 'Current Node joined', 3)
  if key_line == -1:
    return -1;
  return p_v


def SetupRoutingNodes(peer, num_vaults, num_clients):
  print("Setup " + str(num_vaults) + " vaults and " + str(num_clients) + " clients, please wait ....")
  p_nodes = range(num_vaults + num_clients)
  i = 0;
  while i < (num_vaults + num_clients):
    if i < num_vaults:
      p_nodes[i] = AddRoutingObject(peer, i + num_of_bootstraps)
    if i >= num_vaults:
      p_nodes[i] = AddRoutingObject(peer, (num_of_nodes / 2) + (i - num_vaults))
    if p_nodes[i] == -1:
      print 'Failed to add routing object ' + str(i + num_of_bootstraps) + ' !'
      #TODO cleanup the previous opened nodes
      return -1
    i = i + 1
    sleep(1)
  return p_nodes


def StopNodes(p_nodes):
  for p_node in p_nodes:
    p_node.stdin.write('exit' + '\n')
  sleep(1)
  if p_node.poll() == None:
    print "Failed to stop a node!"
  return 0    


def CheckClientNodeIsNotInRoutingTable(p_c):
  for index in range(num_of_nodes / 2):
    p_c.stdin.write('rrt ' + str(index) + '\n')
    sleep(1)
    p_c.stdin.write('\n')
    p_c.stdin.write('\n')
    next_line = SearchKeyWordLine(p_c, 'Sending a msg from ', 2)
    node_id = ((next_line.split(':')[1]).split(' ')[1])
    # print 'checking routing , node_id : ' + node_id
    next_line = p_c.stdout.readline()
    while next_line.find('Enter command >') == -1:
      # print 'checking routing in ' + str(index) + '\t' + next_line.rstrip()
      next_line = p_c.stdout.readline()
      if next_line.find(node_id) != -1:
        return -1
  return 0


def SendGroup(p, target):
  if target != -1:
    p.stdin.write('sendgroup ' + str(target) + '\n')
  else:
    p.stdin.write('sendgroup' + '\n')
  sleep(1)
  p.stdin.write('\n')
  p.stdin.write('\n')
  # TODO: detailed check if respondents are really expected
  if SearchKeyWordLine(p, 'Received response', 5) == -1:
    return -1
  return 0


def SendDirectMsg(p_n, dst, datasize):
  p_n.stdin.write('datasize ' + str(datasize) + '\n')
  p_n.stdin.write('senddirect ' + str(dst) + '\n')
  key_line = SearchKeyWordLine(p_n, 'Response received in', 10)
  if key_line == -1:
    print("Failed in sending a msg to " + str(dst))
    return -1;
  duration = key_line.split()[3]
  print("\t"+ str(datasize) + " Bytes data exchanged in " + duration + " seconds")
  return ParseSecondsFromString(duration)


def JAV1(peer):
  print("Running Routing Sanity Check JAV1 Test, please wait ....")
  p_v = AddRoutingObject(peer, 2)
  if p_v == -1:
    print 'Failed to add routing object!'
    return -1
  p_v.stdin.write('exit' + '\n')
  sleep(2)
  if p_v.poll() == None:
    print "Failed to stop node 2!"
    return -1
  return 0


def JAV2(peer):
  print("Running Routing Sanity Check JAV2 Test, please wait ....")
  p_v = AddRoutingObject(peer, 8)
  if p_v == -1:
    print 'Failed to add routing object!'
    return -1
  result = 0
  if SendDirectMsg(p_v, 1, 1024) == -1:
    result = -1

  p_v.stdin.write('exit' + '\n')
  sleep(2)
  if p_v.poll() == None:
    print "Failed to stop node 2!"
    return -1

  return result


def P1(p_nodes):
  if p_nodes == -1:
    return -1;
  print("Running Routing Sanity Check P1 Test, please wait ....")
  duration = 0
  num_iteration = 5
  for i in range(num_iteration): # vault to vault
    source = random.randint(0, num_of_nodes / 2 - 1)
    dest = random.randint(0, num_of_nodes / 2 - 1) # dest can be a bootstrap node
    if dest != source: # send to self will be super quick, shall be excluded
      print("\tSending a 1MB msg from " + str(source) + " to " + str(dest) + ", please wait ...")
      result = SendDirectMsg(p_nodes[source], dest, 1048576)
      if result == -1:
        return -1
      duration = duration + result
    else:
      i = i - 1
  print('\tAverage transmission time of 1 MB data from vault to vault is : ' + str(duration / num_iteration))

  duration = 0
  for i in range(num_iteration): # client to vault
    source = random.randint(num_of_nodes / 2, num_of_nodes - 1)
    dest = random.randint(0, num_of_nodes / 2 - 1) # dest can be a bootstrap node
    print("\tSending a 1MB msg from " + str(source) + " to " + str(dest) + ", please wait ...")
    result = SendDirectMsg(p_nodes[source], dest, 1048576)
    if result == -1:
      return -1
    duration = duration + result
  print('\tAverage transmission time of 1 MB data from client to vault is : ' + str(duration / num_iteration))
  return 0


def JAC1(peer):
  print("Running Routing Sanity Check JAC1 Test, please wait ....")
  p_c = AddRoutingObject(peer, 12)
  result = 0
  if p_c == -1:
    print 'Failed to add routing object!'
    return -1
  if SendDirectMsg(p_c, 12, 1024) != -1:
    print 'Client shall not be able to send to itself'
    result = -1

  if SendDirectMsg(p_c, 5, 1024) == -1:
    print 'Client failed to send to vault 5'
    result = -1
  if CheckClientNodeIsNotInRoutingTable(p_c) == -1:
    result = -1
  p_c.stdin.write('exit' + '\n')
  sleep(2)
  if p_c.poll() == None:
    print "Failed to stop node 12!"
    return -1
  return result


def JAC2(peer, p_nodes):
  print("Running Routing Sanity Check JAC2 Test, please wait ....")
  v_drop = 3
  # drop the vault first
  p_nodes[v_drop].stdin.write('exit' + '\n')
  sleep(1)
  if p_nodes[v_drop].poll() == None:
    print "Failed to stop a node!"
  # join the node back
  p_nodes[v_drop] = AddRoutingObject(peer, 2)
  if p_nodes[v_drop] == -1:
    print "Failed to join the dropped node back!"
    return -1
  # check routing table
  result = 0
  for i in range(num_of_nodes / 2, num_of_nodes):
    # print '----------------- :' + str(i)
    if CheckClientNodeIsNotInRoutingTable(p_nodes[i]) == -1:
      result = -1
  return result

def  SGM1(p_nodes):
  print("Running Routing Sanity Check SGM1 Test, please wait ....")
  num_iteration = 5
  for i in range(num_iteration):
    rnd = random.randint(0, num_of_nodes / 2 - 1)
    if SendGroup(p_nodes[rnd], -1) != 0:
      return -1
    target = random.randint(0, num_of_nodes - 1)
    if SendGroup(p_nodes[rnd], target) != 0:
      return -1
  return 0


def SanityCheck():
  print("Running Routing Sanity Check, please wait ....")

  if not SetupKeys(num_of_nodes) == 0:
    return -1
  items = SetupBootstraps()
  if items == -1:
    return -1
  peer = items[0]
  p_bs = [items[1], items[2]]

  if JAV1(peer) == 0:
    print 'Routing Sanity Check  Test JAV1  : PASSED\n'
  else:
    print 'Routing Sanity Check  Test JAV1  : FAILED\n'

  if JAV2(peer) == 0:
    print 'Routing Sanity Check  Test JAV2  : PASSED\n'
  else:
    print 'Routing Sanity Check  Test JAV2  : FAILED\n'

  p_vaults = SetupRoutingNodes(peer, num_of_vaults, 0)
  if JAC1(peer) == 0:
    print 'Routing Sanity Check  Test JAC1  : PASSED\n'
  else:
    print 'Routing Sanity Check  Test JAC1  : FAILED\n'

  p_clients = SetupRoutingNodes(peer, 0, num_of_clients)
  p_nodes = p_bs + p_vaults + p_clients

  if SGM1(p_nodes) == 0:
    print 'Routing Sanity Check  Test SGM1  : PASSED\n'
  else:
    print 'Routing Sanity Check  Test SGM1  : FAILED\n'

  if P1(p_nodes) == 0:
    print 'Routing Sanity Check  Test P1  : PASSED\n'
  else:
    print 'Routing Sanity Check  Test P1  : FAILED\n'

  if JAC2(peer, p_nodes) == 0:
    print 'Routing Sanity Check  Test JAC2  : PASSED\n'
  else:
    print 'Routing Sanity Check  Test JAC2  : FAILED\n'

  StopNodes(p_nodes)


def main():
  print("This is the suite for lifestuff Qa analysis")
  SanityCheck()

if __name__ == "__main__":
  sys.exit(main())
